"""
GDPR data-export view, rate-limiting helpers, and the profile page render.
"""

import json
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.views import APIView

from auditableEntity.models import AuditEntry
from user.models import User, UserDataExportLog

logger = logging.getLogger(__name__)


def profile(request):
    """Render the user profile page, injecting data-export rate-limit context.
    Input: request - HttpRequest
    Output: HttpResponse with the profile template and export config values
    """
    cooldown_seconds = _get_export_cooldown_seconds()
    return render(
        request,
        "profile/profile.html",
        {
            "show_authenticated_footer": True,
            "export_cooldown_minutes": cooldown_seconds // 60,
        },
    )


def _get_export_cooldown_seconds():
    """Read data-export cooldown setting with a safe minimum default.
    Input: None; reads DATA_EXPORT_COOLDOWN_SECONDS from settings
    Output: int seconds clamped to a minimum of 60
    """
    return max(60, int(getattr(settings, "DATA_EXPORT_COOLDOWN_SECONDS", 600)))


_EXPORT_WINDOW_LIMIT = 2  # exports allowed per cooldown window before rate-limiting


def _check_export_cooldown(user_id):
    """Check whether a user has exhausted their export quota for the current window.
    Input: user_id - int/str primary key of the requesting user
    Output: tuple (limited: bool, retry_after: int seconds remaining in cooldown)
    """
    cooldown = _get_export_cooldown_seconds()
    key = f"gdpr_export_cooldown:{user_id}"
    data = cache.get(key)
    if not isinstance(data, dict):
        return False, 0
    count = data.get("count", 0)
    if count < _EXPORT_WINDOW_LIMIT:
        return False, 0
    elapsed = int(time.time()) - int(data.get("ts", int(time.time())))
    retry_after = cooldown - elapsed
    return (retry_after > 0), max(1, retry_after)


def _start_export_cooldown(user_id):
    """Increment the export counter for the current window, opening one if needed.
    Input: user_id - int/str primary key of the requesting user
    Output: None
    """
    cooldown = _get_export_cooldown_seconds()
    key = f"gdpr_export_cooldown:{user_id}"
    data = cache.get(key)
    if not isinstance(data, dict):
        data = {"count": 0, "ts": int(time.time())}
    data["count"] = data.get("count", 0) + 1
    cache.set(key, data, timeout=cooldown)


def _build_export_payload(user):
    """Assemble the GDPR personal-data export payload for a given user.
    Input: user - User instance whose data is being exported
    Output: dict with 'metadata', 'personal_data', and 'activity' (last 100 audit entries) sections
    """
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


def _safe_create_export_log(*, user, outcome, notes=""):
    """Persist a data-export audit log entry, swallowing any storage errors.
    Input: user - User instance; outcome - UserDataExportLog.Outcome value; notes - str
    Output: None; side-effect: creates a UserDataExportLog row, or logs exception on failure
    """
    try:
        UserDataExportLog.objects.create(
            user=user,
            outcome=outcome,
            notes=notes,
        )
    except Exception:
        logger.exception("Could not persist user data export audit log")


class ProfileExportDataView(APIView):
    """API endpoint for authenticated users to download their personal data as a JSON file."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Generate and stream a GDPR personal-data export for the requesting user.
        Input: request - authenticated HttpRequest
        Output: HttpResponse with a JSON attachment on success, or JsonResponse with error on rate limit or failure
        """
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

        limited, retry_after = _check_export_cooldown(user.pk)
        if limited:
            _safe_create_export_log(
                user=user,
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

            _start_export_cooldown(user.pk)
            _safe_create_export_log(
                user=user,
                outcome=UserDataExportLog.Outcome.SUCCESS,
                notes="Personal data exported successfully.",
            )
            return response
        except Exception:
            _safe_create_export_log(
                user=user,
                outcome=UserDataExportLog.Outcome.ERROR,
                notes="Unexpected server error during export generation.",
            )
            return JsonResponse(
                {"detail": "Unable to generate export file at this time."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
