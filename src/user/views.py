import hashlib
import json
import logging
import time

from django.apps import apps
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from auditableEntity.audit import (
    AuditActionType,
    create_audit_entry,
    suppress_audit_events,
)
from auditableEntity.models import AuditEntry
from common.drf import AuditActorViewMixin
from common.errors.exceptions import (
    ResourceConflictError,
    ValidationAppError,
)
from common.permissions import IsManagementUser
from common.tenancy import get_active_team
from main.views import render_admin_dashboard
from securityIncident.models import SecurityIncident
from user.models import (
    CollaborationTeam,
    CollaborationTeamInvitation,
    CollaborationTeamInvitationStatus,
    User,
    UserDataExportLog,
)
from user.serializers import (
    CollaborationTeamCreateSerializer,
    CollaborationTeamInvitationRespondSerializer,
    CollaborationTeamInvitationSerializer,
    CollaborationTeamInviteSerializer,
    LoginSerializer,
    UserAccountDeletionSerializer,
    UserChangePasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)


def sign_in(request):
    return render(request, "auth/login.html")


def sign_up(request):
    return render(request, "auth/signup.html")


def admin_users(request):
    state = {
        "title": "Usuarios del equipo",
        "description": "Consulta los usuarios de tu equipo activo.",
        "empty_message": "No hay usuarios en el equipo activo.",
    }

    return render_admin_dashboard(
        request,
        "users",
        {
            "dashboard_admin_state": state,
        },
    )


def _extract_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _get_export_rate_limit_config():
    max_requests = int(getattr(settings, "DATA_EXPORT_RATE_LIMIT_MAX_REQUESTS", 3))
    window_seconds = int(
        getattr(settings, "DATA_EXPORT_RATE_LIMIT_WINDOW_SECONDS", 3600)
    )
    return max(1, max_requests), max(60, window_seconds)


def _consume_export_rate_limit(user_id):
    """Consume one export token from a per-user fixed window bucket."""
    max_requests, window_seconds = _get_export_rate_limit_config()
    now = int(time.time())
    window_id = now // window_seconds
    key = f"gdpr_export:{user_id}:{window_id}"

    if cache.add(key, 1, timeout=window_seconds):
        return False, max_requests - 1, window_seconds

    try:
        current_count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        current_count = 1

    remaining = max(0, max_requests - current_count)
    limited = current_count > max_requests
    retry_after = window_seconds - (now % window_seconds)
    return limited, remaining, retry_after


def _build_export_payload(user):
    activity_items = []
    audit_entries = AuditEntry.objects.filter(actor=user).order_by("-occurred_at")[:100]

    for entry in audit_entries:
        action_text = entry.detail.strip() if entry.detail else ""
        if not action_text:
            entity_label = entry.entity_name or entry.entity_type
            action_text = f"{entry.action_type} {entity_label}".strip()

        activity_items.append(
            {
                "action": action_text,
                "date": entry.occurred_at.isoformat(),
                "detail": entry.detail or "",
            }
        )

    return {
        "metadata": {
            "exported_at": timezone.now().isoformat(),
        },
        "personal_data": {
            "username": user.name,
            "email": user.email,
            "family_name": user.family_name,
            "active_team": user.active_team.name if user.active_team else None,
        },
        "activity": activity_items,
    }


def _safe_create_export_log(*, user, request, outcome, notes=""):
    try:
        UserDataExportLog.objects.create(
            user=user,
            ip_address=_extract_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
            outcome=outcome,
            notes=notes,
        )
    except Exception:
        logger.exception("Could not persist user data export audit log")


def _build_deleted_account_email(user):
    payload = f"{settings.SECRET_KEY}:{user.pk}:{user.email}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"deleted-{digest[:24]}@deleted.invalid"


def _clear_user_sessions(user_id):
    for session in Session.objects.all().iterator():
        try:
            decoded = session.get_decoded()
        except Exception:
            continue
        if str(decoded.get("_auth_user_id")) == str(user_id):
            session.delete()


def _blacklist_user_refresh_tokens(user):
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def _anonymize_authorship_fields(*, original_email, anonymized_email):
    original_email = (original_email or "").strip()
    anonymized_email = (anonymized_email or "").strip()
    if not original_email or not anonymized_email:
        return

    for model in apps.get_models():
        field_names = {field.name for field in model._meta.concrete_fields}
        if "created_by" in field_names:
            model.objects.filter(created_by__iexact=original_email).update(
                created_by=anonymized_email
            )
        if "updated_by" in field_names:
            model.objects.filter(updated_by__iexact=original_email).update(
                updated_by=anonymized_email
            )


def _cleanup_related_user_records(user, *, original_email, anonymized_email):
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


def profile(request):
    return render(
        request,
        "profile/profile.html",
        {
            "show_authenticated_footer": True,
            "export_rate_limit_max_requests": _get_export_rate_limit_config()[0],
            "export_rate_limit_window_minutes": _get_export_rate_limit_config()[1]
            // 60,
        },
    )


class ProfileExportDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            user = User.objects.get(pk=request.user.pk)
        except User.DoesNotExist:
            return JsonResponse(
                {"detail": "Authenticated user not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Explicit ownership verification (defense in depth), even with token auth.
        if user.pk != request.user.pk:
            return JsonResponse(
                {"detail": "You can only export your own personal data."},
                status=status.HTTP_403_FORBIDDEN,
            )

        limited, _remaining, retry_after = _consume_export_rate_limit(user.pk)
        if limited:
            _safe_create_export_log(
                user=user,
                request=request,
                outcome=UserDataExportLog.Outcome.RATE_LIMITED,
                notes="Rate limit exceeded while requesting personal data export.",
            )
            response = JsonResponse(
                {
                    "detail": (
                        "Rate limit exceeded for data export. "
                        "Please wait before requesting again."
                    )
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(max(1, retry_after))
            return response

        try:
            payload = _build_export_payload(user)
            body = json.dumps(payload, ensure_ascii=False, indent=2)
            filename = (
                f"orarioo-personal-data-{user.pk}-{timezone.now():%Y%m%dT%H%M%SZ}.json"
            )

            response = HttpResponse(
                body, content_type="application/json; charset=utf-8"
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
            response["X-Content-Type-Options"] = "nosniff"

            _safe_create_export_log(
                user=user,
                request=request,
                outcome=UserDataExportLog.Outcome.SUCCESS,
                notes="Personal data exported successfully.",
            )
            return response
        except Exception:
            _safe_create_export_log(
                user=user,
                request=request,
                outcome=UserDataExportLog.Outcome.ERROR,
                notes="Unexpected server error during export generation.",
            )
            return JsonResponse(
                {"detail": "Unable to generate export file at this time."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserAccountDeletionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserAccountDeletionSerializer(
            data=request.data,
            context={"request": request},
        )
        return _erase_user_account(request, request.user, serializer)


class UserSelfUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom view to obtain JWT tokens"""

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class SetActiveTeamView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        team_id = request.data.get("team_id") or request.data.get("active_team")
        if not team_id:
            raise ValidationAppError(
                "REQUIRED_FIELD",
                "team_id is required.",
                field_name="team_id",
                context={"field": "team_id"},
            )

        try:
            team_id = int(team_id)
        except (TypeError, ValueError):
            raise ValidationAppError(
                "INVALID_INTEGER",
                "team_id must be a valid integer.",
                field_name="team_id",
                context={"field": "team_id", "value": team_id},
            )

        team = request.user.collaboration_teams.filter(id=team_id).first()
        if team is None:
            raise ValidationAppError(
                "TEAM_NOT_MEMBER",
                "The selected team does not belong to the user.",
                field_name="team_id",
                context={"field": "team_id", "team_id": team_id},
            )

        request.user.active_team = team
        request.user.save(update_fields=["active_team"])

        return Response(
            {"user": UserSerializer(request.user).data},
            status=status.HTTP_200_OK,
        )


class CollaborationTeamCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CollaborationTeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        team = CollaborationTeam.objects.create(name=serializer.validated_data["name"])
        team.members.add(request.user)

        if request.user.active_team_id is None:
            request.user.active_team = team
            request.user.save(update_fields=["active_team"])

        return Response(
            {
                "team": {
                    "id": team.id,
                    "name": team.name,
                },
                "user": UserSerializer(request.user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CollaborationTeamInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CollaborationTeamInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        team_id = serializer.validated_data.get("team_id")
        if team_id:
            team = request.user.collaboration_teams.filter(id=team_id).first()
        else:
            team = request.user.active_team
            if team is None:
                team = request.user.collaboration_teams.order_by("name", "id").first()

        if team is None:
            raise ValidationAppError(
                "ACTIVE_TEAM_REQUIRED",
                "No active collaboration team found. Create or select a team first.",
            )

        email = serializer.validated_data["email"]
        invited_user = User.objects.filter(email=email, is_enabled=True).first()
        if invited_user is None:
            raise ValidationAppError(
                "INVITED_USER_NOT_FOUND",
                "No active user exists with that email. Ask that person to sign up first.",
                field_name="email",
                context={"field": "email", "value": email},
            )

        if team.members.filter(id=invited_user.id).exists():
            raise ResourceConflictError(
                "USER_ALREADY_IN_TEAM",
                "The user already belongs to this collaboration team.",
                context={
                    "email": email,
                    "team_id": team.id,
                    "team_name": team.name,
                },
            )

        pending_exists = CollaborationTeamInvitation.objects.filter(
            team=team,
            invited_user=invited_user,
            status=CollaborationTeamInvitationStatus.PENDING,
        ).exists()
        if pending_exists:
            raise ResourceConflictError(
                "INVITATION_ALREADY_PENDING",
                "There is already a pending invitation for this user in the selected collaboration team.",
                context={
                    "email": email,
                    "team_id": team.id,
                    "team_name": team.name,
                },
            )

        invitation = CollaborationTeamInvitation.objects.create(
            team=team,
            invited_user=invited_user,
            invited_by=request.user,
            status=CollaborationTeamInvitationStatus.PENDING,
        )

        return Response(
            {
                "team": {"id": team.id, "name": team.name},
                "invited_user": UserSerializer(invited_user).data,
                "invitation": CollaborationTeamInvitationSerializer(invitation).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CollaborationTeamInvitationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        invitations = CollaborationTeamInvitation.objects.filter(
            invited_user=request.user
        ).select_related("team", "invited_by")
        serializer = CollaborationTeamInvitationSerializer(invitations, many=True)
        pending_count = sum(
            1
            for item in serializer.data
            if item["status"] == CollaborationTeamInvitationStatus.PENDING
        )
        return Response(
            {
                "count": len(serializer.data),
                "pending_count": pending_count,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class CollaborationTeamInvitationRespondView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        invitation = (
            CollaborationTeamInvitation.objects.filter(
                id=invitation_id,
                invited_user=request.user,
            )
            .select_related("team")
            .first()
        )
        if invitation is None:
            return Response(
                {"detail": "Invitation not found for current user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.status != CollaborationTeamInvitationStatus.PENDING:
            return Response(
                {"detail": "This invitation was already answered."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CollaborationTeamInvitationRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.to_status()

        if new_status == CollaborationTeamInvitationStatus.ACCEPTED:
            invitation.team.members.add(request.user)

        invitation.status = new_status
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        return Response(
            {
                "invitation": CollaborationTeamInvitationSerializer(invitation).data,
                "user": UserSerializer(request.user).data,
            },
            status=status.HTTP_200_OK,
        )


class CollaborationTeamLeaveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        raw_team_id = request.data.get("team_id") or getattr(
            request.user.active_team, "id", None
        )
        if not raw_team_id:
            raise ValidationAppError(
                "ACTIVE_TEAM_REQUIRED",
                "No team selected to leave.",
            )

        try:
            team_id = int(raw_team_id)
        except (TypeError, ValueError):
            raise ValidationAppError(
                "INVALID_INTEGER",
                "team_id must be a valid integer.",
                field_name="team_id",
                context={"field": "team_id", "value": raw_team_id},
            )

        team = request.user.collaboration_teams.filter(id=team_id).first()
        if team is None:
            raise ValidationAppError(
                "TEAM_NOT_MEMBER",
                "You do not belong to the selected team.",
                field_name="team_id",
                context={"field": "team_id", "team_id": team_id},
            )

        team.members.remove(request.user)

        if request.user.active_team_id == team.id:
            next_team = request.user.collaboration_teams.order_by("name", "id").first()
            request.user.active_team = next_team
            request.user.save(update_fields=["active_team"])

        if not team.members.exists():
            team.delete()

        return Response(
            {"user": UserSerializer(request.user).data},
            status=status.HTTP_200_OK,
        )


class UserViewSet(AuditActorViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing users.

    Available operations:
    - GET /api/users/ - List all users
    - POST /api/users/ - Create new user (signup)
    - GET /api/users/{id}/ - Get user details
    - POST /api/users/change_password/ - Change password
    - POST /api/users/me/ - Get current user data
    """

    class UserPagination(PageNumberPagination):
        page_size = 9
        page_size_query_param = "page_size"
        max_page_size = 100

    queryset = User.objects.filter(is_enabled=True).order_by("-created_at")
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = UserPagination
    http_method_names = ["get", "post", "head", "options"]
    serializer_action_classes = {
        "create": UserCreateSerializer,
        "change_password": UserChangePasswordSerializer,
    }

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "signup"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        """Returns the appropriate serializer based on the action"""
        return self.serializer_action_classes.get(self.action, UserSerializer)

    def get_permissions(self):
        """Defines permissions based on the action"""
        if self.action == "create":
            # Allow creating users (signup)
            return [permissions.AllowAny()]
        if self.action in ["list", "retrieve"]:
            # Team-scoped management is available to authenticated users.
            return [IsManagementUser()]
        if self.action in ["change_password", "me"]:
            # Authenticated user can change their password
            return [permissions.IsAuthenticated()]

        return super().get_permissions()

    def get_queryset(self):
        """Return enabled users from the authenticated user's active team."""
        try:
            active_team = get_active_team(self.request)
        except PermissionDenied:
            return User.objects.none()

        return (
            User.objects.filter(
                is_enabled=True,
                collaboration_teams=active_team,
            )
            .distinct()
            .order_by("-created_at")
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="me",
    )
    def me(self, request):
        """Gets the current authenticated user data"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="change_password",
    )
    def change_password(self, request):
        """Allows user to change their password"""
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        # Generate new tokens after password change
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "success": True,
                "message": _("Password updated successfully"),
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="logout",
    )
    def logout(self, request):
        """Logs out the user and blacklists refresh token"""
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": _("Refresh token is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"detail": _("Invalid refresh token.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": _("Session closed successfully")},
            status=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        """Allows creating users without authentication (signup)"""
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            # Generate tokens automatically after registration
            user = User.objects.get(email=response.data["email"])
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "user": response.data,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_201_CREATED,
            )

        return response
