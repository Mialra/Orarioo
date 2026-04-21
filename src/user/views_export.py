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
    max_requests, window_seconds = _get_export_rate_limit_config()
    return render(
        request,
        "profile/profile.html",
        {
            "show_authenticated_footer": True,
            "export_rate_limit_max_requests": max_requests,
            "export_rate_limit_window_minutes": window_seconds // 60,
        },
    )


def _get_export_rate_limit_config():
    """Read data-export rate-limit settings with safe minimum defaults.
    Input: None; reads DATA_EXPORT_RATE_LIMIT_MAX_REQUESTS and DATA_EXPORT_RATE_LIMIT_WINDOW_SECONDS from settings
    Output: tuple (max_requests: int, window_seconds: int) clamped to minimums of 1 and 60
    """
    max_requests = int(getattr(settings, "DATA_EXPORT_RATE_LIMIT_MAX_REQUESTS", 3))
    window_seconds = int(
        getattr(settings, "DATA_EXPORT_RATE_LIMIT_WINDOW_SECONDS", 3600)
    )
    return max(1, max_requests), max(60, window_seconds)


def _consume_export_rate_limit(user_id):
    """Consume one export token from a per-user fixed-window rate-limit bucket.
    Input: user_id - int/str primary key of the requesting user
    Output: tuple (limited: bool, remaining: int, retry_after: int seconds until window resets)
    """
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

        limited, _remaining, retry_after = _consume_export_rate_limit(user.pk)
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
