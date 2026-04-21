"""
Collaboration team management views: create, invite, respond to invitations, and leave a team.
"""

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors.exceptions import ResourceConflictError, ValidationAppError
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
