"""
Account deletion view and supporting helpers for anonymization and session cleanup.
"""

import hashlib
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from auditableEntity.audit import (
    AuditActionType,
    create_audit_entry,
    suppress_audit_events,
)
from auditableEntity.models import AuditEntry
from securityIncident.models import SecurityIncident
from user.models import CollaborationTeamInvitation, User, UserDataExportLog
from user.serializers import UserAccountDeletionSerializer

logger = logging.getLogger(__name__)


def _build_deleted_account_email(user):
    """Derive a deterministic, unguessable anonymized email address for a deleted user.
    Input: user - User instance being deleted
    Output: str email in the form 'deleted-<sha256_prefix>@deleted.invalid'
    """
    payload = f"{settings.SECRET_KEY}:{user.pk}:{user.email}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"deleted-{digest[:24]}@deleted.invalid"


def _clear_user_sessions(user_id):
    """Invalidate all active Django sessions belonging to the given user.
    Input: user_id - int/str primary key of the user whose sessions should be cleared
    Output: None; side-effect: deletes matching Session rows
    """
    for session in Session.objects.all().iterator():
        try:
            decoded = session.get_decoded()
        except Exception:
            continue
        if str(decoded.get("_auth_user_id")) == str(user_id):
            session.delete()


def _blacklist_user_refresh_tokens(user):
    """Blacklist all outstanding JWT refresh tokens for the given user.
    Input: user - User instance
    Output: None; side-effect: creates BlacklistedToken entries for all outstanding tokens
    """
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def _anonymize_authorship_fields(*, original_email, anonymized_email):
    """Replace the user's email in created_by/updated_by fields across all auditable models.
    Input: original_email - str email to replace; anonymized_email - str replacement email
    Output: None; side-effect: bulk-updates created_by and updated_by columns across the database
    """
    original_email = (original_email or "").strip()
    anonymized_email = (anonymized_email or "").strip()
    if not original_email or not anonymized_email:
        return

    for model in apps.get_models():
        fields_by_name = {field.name: field for field in model._meta.concrete_fields}
        for attr in ("created_by", "updated_by"):
            field = fields_by_name.get(attr)
            if field is not None and isinstance(field, models.CharField):
                model.objects.filter(**{f"{attr}__iexact": original_email}).update(
                    **{attr: anonymized_email}
                )


def _cleanup_related_user_records(user, *, original_email, anonymized_email):
    """Anonymize and sever all database relationships tied to a user being deleted.
    Input: user - User instance; original_email - str current email; anonymized_email - str replacement email
    Output: None; side-effect: removes team memberships, invitations, schedules, and anonymizes audit records
    """
    schedule_ids = list(user.schedules.values_list("id", flat=True))
    if schedule_ids:
        with suppress_audit_events(("schedule", AuditActionType.UPDATE)):
            user.schedules.clear()

    _anonymize_authorship_fields(
        original_email=original_email,
        anonymized_email=anonymized_email,
    )

    collaboration_teams = list(user.collaboration_teams.all())
    for team in collaboration_teams:
        team.members.remove(user)

    UserDataExportLog.objects.filter(user=user).delete()
    CollaborationTeamInvitation.objects.filter(
        Q(invited_user=user) | Q(invited_by=user)
    ).delete()

    SecurityIncident.objects.filter(user=user).update(
        user=None,
        description="Registro anonimizado tras la eliminación de la cuenta.",
    )

    AuditEntry.objects.filter(actor=user).update(
        actor=None,
        actor_name="Usuario eliminado",
    )
    AuditEntry.objects.filter(entity_type="user", entity_id=user.pk).update(
        entity_name="Usuario eliminado",
        detail="Registro anonimizado tras la eliminación de la cuenta.",
        changed_fields=[],
    )


def _erase_user_account(request, user, serializer):
    """Validate the deletion request and irreversibly anonymize the user account inside a transaction.
    Input: request - HttpRequest; user - User instance to delete; serializer - UserAccountDeletionSerializer instance
    Output: Response with deletion confirmation, or error Response if the account was already deleted
    """
    serializer.is_valid(raise_exception=True)

    if user.deleted_at is not None:
        return Response(
            {"detail": "This account has already been deleted."},
            status=status.HTTP_410_GONE,
        )

    original_team = user.active_team

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.deleted_at is not None:
            return Response(
                {"detail": "This account has already been deleted."},
                status=status.HTTP_410_GONE,
            )

        original_email = user.email
        anonymized_email = _build_deleted_account_email(user)

        _cleanup_related_user_records(
            user,
            original_email=original_email,
            anonymized_email=anonymized_email,
        )

        user.name = "Usuario eliminado"
        user.family_name = ""
        user.email = anonymized_email
        user.password = None
        user.is_enabled = False
        user.active_team = None
        user.deleted_at = timezone.now()

        with suppress_audit_events(("user", AuditActionType.UPDATE)):
            user.save(
                update_fields=[
                    "name",
                    "family_name",
                    "email",
                    "password",
                    "is_enabled",
                    "active_team",
                    "deleted_at",
                    "updated_at",
                ]
            )

        create_audit_entry(
            model=User,
            entity_id=user.pk,
            entity_name="Usuario eliminado",
            action_type=AuditActionType.DELETE,
            detail="Se eliminó y anonimizó la cuenta de usuario.",
            changed_fields=[
                {"campo": "Cuenta", "valor_nuevo": "anonimizada"},
                {"campo": "Eliminada en", "valor_nuevo": user.deleted_at.isoformat()},
            ],
            team=original_team,
        )

        _blacklist_user_refresh_tokens(user)
        _clear_user_sessions(user.pk)

    logger.info("User account deleted", extra={"user_id": user.pk})
    return Response(
        {
            "detail": "Your account has been permanently deleted.",
            "deleted_at": user.deleted_at,
        },
        status=status.HTTP_200_OK,
    )


class UserAccountDeletionView(APIView):
    """API endpoint for authenticated users to permanently delete their own account."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Accept and process a self-service account deletion request.
        Input: request - authenticated HttpRequest with confirmation_text in body
        Output: Response confirming deletion, or error Response if preconditions fail
        """
        serializer = UserAccountDeletionSerializer(
            data=request.data,
            context={"request": request},
        )
        return _erase_user_account(request, request.user, serializer)
