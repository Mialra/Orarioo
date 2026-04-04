from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.drf import AuditActorViewMixin
from common.tenancy import get_active_team
from common.permissions import IsManagementUser
from main.views import render_admin_dashboard
from user.models import (
    CollaborationTeam,
    CollaborationTeamInvitation,
    CollaborationTeamInvitationStatus,
    RoleChoices,
    User,
)
from user.serializers import (
    CollaborationTeamCreateSerializer,
    CollaborationTeamInvitationRespondSerializer,
    CollaborationTeamInvitationSerializer,
    CollaborationTeamInviteSerializer,
    LoginSerializer,
    UserChangePasswordSerializer,
    UserCreateSerializer,
    UserManagementCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


def sign_in(request):
    return render(request, "auth/login.html")


def sign_up(request):
    return render(request, "auth/signup.html")


def admin_users(request):
    users = User.objects.filter(is_enabled=True).order_by("-created_at")
    state = {
        "title": "Gestión de Usuarios",
        "description": "Administra el personal del centro, sus accesos y sus roles.",
        "empty_message": "No hay usuarios registrados. Añade el primero para comenzar.",
        "add_cta": "Añadir Usuario",
    }

    return render_admin_dashboard(
        request,
        "users",
        {
            "dashboard_admin_state": state,
            "dashboard_admin_users": users,
        },
    )


class IsAdministratorOrSelf(permissions.BasePermission):
    """Permission for administrators or the user themselves to access"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return request.user.is_administrator() or obj.id == request.user.id


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
            return Response(
                {"team_id": "team_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            team_id = int(team_id)
        except (TypeError, ValueError):
            return Response(
                {"team_id": "team_id must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = request.user.collaboration_teams.filter(id=team_id).first()
        if team is None:
            return Response(
                {"team_id": "The selected team does not belong to the user."},
                status=status.HTTP_400_BAD_REQUEST,
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
            return Response(
                {
                    "detail": (
                        "No active collaboration team found. "
                        "Create or select a team first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        invited_user = User.objects.filter(email=email, is_enabled=True).first()
        if invited_user is None:
            return Response(
                {
                    "email": (
                        "No active user exists with that email. "
                        "Create the user first from Administracion > Usuarios."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if team.members.filter(id=invited_user.id).exists():
            return Response(
                {"detail": "The user already belongs to this collaboration team."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pending_exists = CollaborationTeamInvitation.objects.filter(
            team=team,
            invited_user=invited_user,
            status=CollaborationTeamInvitationStatus.PENDING,
        ).exists()
        if pending_exists:
            return Response(
                {
                    "detail": (
                        "There is already a pending invitation for this user "
                        "in the selected collaboration team."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
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
        invitation = CollaborationTeamInvitation.objects.filter(
            id=invitation_id,
            invited_user=request.user,
        ).select_related("team").first()
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
            return Response(
                {"detail": "No team selected to leave."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            team_id = int(raw_team_id)
        except (TypeError, ValueError):
            return Response(
                {"team_id": "team_id must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = request.user.collaboration_teams.filter(id=team_id).first()
        if team is None:
            return Response(
                {"detail": "You do not belong to the selected team."},
                status=status.HTTP_400_BAD_REQUEST,
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
    - POST /api/users/ - Create new user
    - GET /api/users/{id}/ - Get user details
    - PUT /api/users/{id}/ - Update complete user
    - PATCH /api/users/{id}/ - Partially update
    - DELETE /api/users/{id}/ - Delete user
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
    serializer_action_classes = {
        "create": UserCreateSerializer,
        "managed_create": UserManagementCreateSerializer,
        "partial_update": UserUpdateSerializer,
        "update": UserUpdateSerializer,
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
        if self.action == "managed_create":
            # Authenticated staff (administrator/direccion) can create managed users
            return [IsManagementUser()]
        if self.action in ["list", "destroy", "update", "partial_update"]:
            # Administrator and direccion have the same management scope.
            return [IsManagementUser()]
        if self.action == "retrieve":
            # User can see their own profile, administrator can see any
            return [IsAdministratorOrSelf()]
        if self.action in ["change_password", "me"]:
            # Authenticated user can change their password
            return [permissions.IsAuthenticated()]

        return super().get_permissions()

    def get_queryset(self):
        """Filters users based on permissions"""
        user = self.request.user

        if user.role in [RoleChoices.ADMINISTRATOR, RoleChoices.DIRECCION]:
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

        # Other users only see their own profile.
        return User.objects.filter(id=user.id, is_enabled=True).order_by("-created_at")

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsManagementUser],
        url_path="managed_create",
    )
    def managed_create(self, request):
        """Creates users for audit/assignment flows with optional login access."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

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

    def perform_update(self, serializer):
        """Updates an existing user"""
        serializer.save()

    def perform_destroy(self, instance):
        """Deletes a user (soft delete - marks as inactive)"""
        instance.is_enabled = False
        instance.save()

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
