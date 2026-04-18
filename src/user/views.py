"""
Core user management views: auth, signup, template renders, and user CRUD viewset.
"""

import logging

from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.drf import AuditActorViewMixin, StandardPagination
from common.tenancy import get_active_team
from main.views import render_admin_dashboard
from user.models import User
from user.serializers import (
    LoginSerializer,
    UserChangePasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)


def sign_in(request):
    """Render the sign-in page.
    Input: request - HttpRequest
    Output: HttpResponse with the login template
    """
    return render(request, "auth/login.html")


def sign_up(request):
    """Render the sign-up page.
    Input: request - HttpRequest
    Output: HttpResponse with the signup template
    """
    return render(request, "auth/signup.html")


def admin_users(request):
    """Render the administration dashboard with the users tab selected.
    Input: request - HttpRequest
    Output: HttpResponse with the admin dashboard template
    """
    return render_admin_dashboard(request, "users")


class UserSelfUpdateView(APIView):
    """API endpoint for authenticated users to update their own profile fields."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Apply a partial update to the requesting user's profile.
        Input: request - authenticated HttpRequest with fields to update in body
        Output: Response with the updated user serialized data
        """
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom login view that returns JWT tokens together with the authenticated user data."""

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        """Authenticate the user and return a refresh/access token pair with user data.
        Input: request - HttpRequest with email and password in body
        Output: Response with refresh token, access token, and serialized user
        """
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
    """CRUD viewset for users with team-scoped listing, signup, auth, and password management."""

    queryset = User.objects.filter(is_enabled=True).order_by("-created_at")
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "head", "options"]
    serializer_action_classes = {
        "create": UserCreateSerializer,
        "change_password": UserChangePasswordSerializer,
    }

    def get_throttles(self):
        """Apply signup-specific rate throttling for the create action.
        Input: self - viewset instance with self.action set
        Output: list of throttle instances; ScopedRateThrottle with 'signup' scope for create, default otherwise
        """
        if self.action == "create":
            self.throttle_scope = "signup"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        """Return the appropriate serializer class based on the current action.
        Input: self - viewset instance with self.action set
        Output: serializer class mapped to the action, or UserSerializer as default
        """
        return self.serializer_action_classes.get(self.action, UserSerializer)

    def get_permissions(self):
        """Return permission classes appropriate for the current action.
        Input: self - viewset instance with self.action set
        Output: list of permission instances; AllowAny for create, IsAuthenticated for everything else
        """
        if self.action == "create":
            return [permissions.AllowAny()]
        if self.action in ["list", "retrieve", "change_password", "me"]:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        """Return enabled users belonging to the authenticated user's active team.
        Input: self - viewset instance with self.request set
        Output: QuerySet of User filtered by active team, or empty queryset if no active team
        """
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
        """Return the serialized data for the currently authenticated user.
        Input: request - authenticated HttpRequest
        Output: Response with the current user's serialized data
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="change_password",
    )
    def change_password(self, request):
        """Change the current user's password and issue new JWT tokens.
        Input: request - authenticated HttpRequest with current_password, new_password, password_confirm
        Output: Response with success flag and new token pair
        """
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
        """Blacklist the provided refresh token to log the user out.
        Input: request - authenticated HttpRequest with refresh token in body
        Output: Response confirming logout, or 400 if token is missing or invalid
        """
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
        """Create a new user account (signup) and return JWT tokens along with user data.
        Input: request - HttpRequest with user registration data in body
        Output: Response with user data and token pair on success
        """
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
