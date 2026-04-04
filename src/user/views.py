from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.drf import AuditActorViewMixin
from common.permissions import IsManagementUser
from main.views import render_admin_dashboard
from user.models import RoleChoices, User
from user.serializers import (
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
            # Administrators and direccion see active users.
            return User.objects.filter(is_enabled=True).order_by("-created_at")

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
