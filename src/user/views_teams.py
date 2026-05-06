"""
Collaboration team management views: create, invite, respond to invitations, and leave a team.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from auditableEntity.audit import AUDITABLE_ENTITY_TYPES, suppress_audit_events
from auditableEntity.models import AuditActionType
from common.errors.exceptions import ResourceConflictError, ValidationAppError
from common.stages import (
    DEFAULT_STAGE_COLORS,
    EducationalStage,
    canonical_group_stage,
    canonical_subject_stage,
)
from common.tenancy import get_active_team
from group.models import Group
from schedule.algorithm.slots import (
    STAGE_SLOT_WINDOWS,
    parse_schedule_config_to_slot_windows,
)
from subject.models import Subject
from user.models import (
    CollaborationTeam,
    CollaborationTeamInvitation,
    CollaborationTeamInvitationStatus,
    User,
)
from user.serializers import (
    CollaborationTeamCreateSerializer,
    CollaborationTeamInvitationRespondSerializer,
    CollaborationTeamInvitationSerializer,
    CollaborationTeamInviteSerializer,
    OnboardingSerializer,
    ScheduleConfigSerializer,
    UserSerializer,
)


class SetActiveTeamView(APIView):
    """API endpoint to switch the authenticated user's active collaboration team."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Set the active collaboration team for the current user.
        Input: request - authenticated HttpRequest with team_id in body
        Output: Response with updated user data, or ValidationAppError on invalid input
        """
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
    """API endpoint to create a new collaboration team and add the creator as its first member."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Create a collaboration team and assign it as the user's active team if they have none.
        Input: request - authenticated HttpRequest with team name in body
        Output: Response with team data and updated user data
        """
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
    """API endpoint to invite an existing registered user to a collaboration team."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Create a pending invitation for a registered user to join a team.
        Input: request - authenticated HttpRequest with email and optional team_id in body
        Output: Response with invitation details, or error if user/team not found or already invited
        """
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
            return Response({}, status=status.HTTP_200_OK)

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
    """API endpoint to list all invitations received by the current user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return all collaboration team invitations addressed to the requesting user.
        Input: request - authenticated HttpRequest
        Output: Response with invitation list, total count, and pending count
        """
        invitations = CollaborationTeamInvitation.objects.filter(
            invited_user=request.user
        ).select_related("team", "invited_by")

        status_filter = (request.query_params.get("status") or "").strip().lower()
        if status_filter:
            allowed_statuses = {
                CollaborationTeamInvitationStatus.PENDING,
                CollaborationTeamInvitationStatus.ACCEPTED,
                CollaborationTeamInvitationStatus.REJECTED,
            }
            if status_filter not in allowed_statuses:
                raise ValidationAppError(
                    "INVALID_CHOICE",
                    "status must be one of: pending, accepted, rejected.",
                    field_name="status",
                    context={"field": "status", "value": status_filter},
                )
            invitations = invitations.filter(status=status_filter)

        summary_mode = (request.query_params.get("summary") or "").strip().lower()
        if summary_mode == "count":
            count = invitations.count()
            pending_count = (
                count
                if status_filter == CollaborationTeamInvitationStatus.PENDING
                else invitations.filter(
                    status=CollaborationTeamInvitationStatus.PENDING
                ).count()
            )
            return Response(
                {
                    "count": count,
                    "pending_count": pending_count,
                },
                status=status.HTTP_200_OK,
            )

        serializer = CollaborationTeamInvitationSerializer(invitations, many=True)
        pending_count = (
            len(serializer.data)
            if status_filter == CollaborationTeamInvitationStatus.PENDING
            else sum(
                1
                for item in serializer.data
                if item["status"] == CollaborationTeamInvitationStatus.PENDING
            )
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
    """API endpoint for a user to accept or reject a received collaboration team invitation."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        """Accept or reject a pending invitation by its ID.
        Input: request - authenticated HttpRequest with accept/reject action; invitation_id - int
        Output: Response with updated invitation and user data, or 404/400 on invalid state
        """
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
    """API endpoint for a user to leave a collaboration team they belong to."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Remove the current user from a collaboration team, deleting it if it becomes empty.
        Input: request - authenticated HttpRequest with optional team_id in body (defaults to active team)
        Output: Response with updated user data, or ValidationAppError if team not found
        """
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

        if request.user.collaboration_teams.count() == 1:
            raise ValidationAppError(
                "LAST_TEAM_CANNOT_LEAVE",
                "You cannot leave your only team. Create or join another team first.",
            )

        team.members.remove(request.user)

        if request.user.active_team_id == team.id:
            next_team = request.user.collaboration_teams.order_by("name", "id").first()
            request.user.active_team = next_team
            request.user.save(update_fields=["active_team"])

        if not team.members.exists():
            suppress_rules = tuple(
                (entity_type, AuditActionType.DELETE)
                for entity_type in AUDITABLE_ENTITY_TYPES
            )
            with suppress_audit_events(*suppress_rules), transaction.atomic():
                team.schedule_schedule_items.all().delete()
                team.subject_subject_items.all().delete()
                team.group_group_items.all().delete()
                team.teacher_teacher_items.all().delete()
                team.classroom_classroom_items.all().delete()
                team.invitations.all().delete()
                team.audit_entries.all().delete()
                team.delete()

        return Response(
            {"user": UserSerializer(request.user).data},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Onboarding and schedule configuration
# ---------------------------------------------------------------------------

_DEFAULT_STAGE_LABELS = {stage.value: stage.label for stage in EducationalStage}


def _stage_labels_from_config(config):
    """Build a {stage_code: label} dict from a schedule_config.
    Input: config - dict of stage configs (may be empty or None)
    Output: dict mapping each stage code to its display label
    """
    if not config:
        return dict(_DEFAULT_STAGE_LABELS)
    return {
        code: (cfg.get("label") or _DEFAULT_STAGE_LABELS.get(code, code))
        for code, cfg in config.items()
    }


def _stage_colors_from_config(config):
    """Build a {stage_code: color} dict from a schedule_config."""
    if not config:
        return dict(DEFAULT_STAGE_COLORS)
    return {
        code: (cfg.get("color") or DEFAULT_STAGE_COLORS.get(code, "blue"))
        for code, cfg in config.items()
    }


def _default_schedule_config():
    """Return the default schedule config derived from STAGE_SLOT_WINDOWS.
    Output: dict {stage_code: {label, start_time, end_time, breaks, session_duration}}
    """
    result = {}
    for stage, windows in STAGE_SLOT_WINDOWS.items():
        lesson_windows = [(s, e) for s, e, is_r in windows if not is_r]
        recess_windows = [(s, e) for s, e, is_r in windows if is_r]
        if not lesson_windows:
            continue
        start_t = lesson_windows[0][0]
        end_t = windows[-1][1]
        first_start, first_end = lesson_windows[0]
        dur = (first_end.hour * 60 + first_end.minute) - (first_start.hour * 60 + first_start.minute)
        result[stage.value] = {
            "label": _DEFAULT_STAGE_LABELS.get(stage.value, stage.value),
            "color": DEFAULT_STAGE_COLORS.get(stage.value, "blue"),
            "start_time": start_t.strftime("%H:%M"),
            "end_time": end_t.strftime("%H:%M"),
            "breaks": [
                {"start": s.strftime("%H:%M"), "end": e.strftime("%H:%M")}
                for s, e in recess_windows
            ],
            "session_duration": dur,
        }
    return result


def _compute_slot_start_times(schedule_config):
    """Return sorted unique lesson-slot start times (HH:MM) for a schedule config.
    Input: schedule_config - dict from CollaborationTeam.schedule_config (may be empty)
    Output: list of HH:MM strings
    """
    windows = parse_schedule_config_to_slot_windows(schedule_config)
    if windows is None:
        windows = {stage: list(entries) for stage, entries in STAGE_SLOT_WINDOWS.items()}
    times = set()
    for stage_windows in windows.values():
        for start_t, _end_t, is_recess in stage_windows:
            if not is_recess:
                times.add(start_t.strftime("%H:%M"))
    return sorted(times)


class OnboardingView(APIView):
    """Create a new collaboration team with schedule config and assign it to the user."""

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """Create team + schedule config atomically and set it as the user's active team.
        Input: request body with team_name (str) and optional schedule_config (dict)
        Output: Response with updated user data on success
        """
        serializer = OnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        team = CollaborationTeam.objects.create(
            name=data["team_name"],
            schedule_config=data.get("schedule_config") or {},
        )
        team.members.add(request.user)
        request.user.active_team = team
        request.user.save(update_fields=["active_team"])

        return Response(UserSerializer(request.user).data, status=status.HTTP_201_CREATED)


class ScheduleConfigView(APIView):
    """Read and update the active team's schedule configuration."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return current schedule config and computed slot start times.
        Output: {schedule_config, slot_start_times}; returns an empty config when no stages are configured
        """
        team = get_active_team(request)
        if team is None:
            return Response(
                {"detail": "No active team."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        config = team.schedule_config or {}
        return Response(
            {
                "schedule_config": config,
                "slot_start_times": _compute_slot_start_times(config),
                "stage_labels": _stage_labels_from_config(config),
                "stage_colors": _stage_colors_from_config(config),
            }
        )

    def put(self, request):
        """Replace the team's schedule config with the validated payload.
        Input: request body with schedule_config dict
        Output: Response with updated {schedule_config, slot_start_times}
        """
        team = get_active_team(request)
        if team is None:
            return Response(
                {"detail": "No active team."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ScheduleConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_config = serializer.validated_data["schedule_config"]
        current_display_config = team.schedule_config or {}
        removed_stages = sorted(
            set(current_display_config.keys()) - set(next_config.keys())
        )
        if removed_stages:
            blocking_group_exists = any(
                canonical_group_stage(group.stage) in removed_stages
                for group in Group.objects.filter(team=team).only("stage")
            )
            blocking_subject_exists = any(
                canonical_subject_stage(subject.stage) in removed_stages
                for subject in Subject.objects.filter(team=team).only("stage")
            )
            if blocking_group_exists or blocking_subject_exists:
                stage_labels = _stage_labels_from_config(current_display_config)
                removed_stage_names = [
                    stage_labels.get(stage, stage) for stage in removed_stages
                ]
                raise ValidationAppError(
                    "STAGE_IN_USE",
                    "No se puede eliminar una etapa que esta siendo usada en cursos o asignaturas.",
                    field_name="schedule_config",
                    context={
                        "stages": removed_stages,
                        "stage_labels": removed_stage_names,
                    },
                )

        team.schedule_config = next_config
        team.save(update_fields=["schedule_config"])
        return Response(
            {
                "schedule_config": team.schedule_config,
                "slot_start_times": _compute_slot_start_times(team.schedule_config),
                "stage_labels": _stage_labels_from_config(team.schedule_config),
                "stage_colors": _stage_colors_from_config(team.schedule_config),
            }
        )
