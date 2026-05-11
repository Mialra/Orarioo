"""
URL routing for user authentication, profile management, and collaboration team endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from user.views import CustomTokenObtainPairView, UserSelfUpdateView, UserViewSet
from user.views_account import UserAccountDeletionView
from user.views_teams import (
    CollaborationTeamCreateView,
    CollaborationTeamInvitationListView,
    CollaborationTeamInvitationRespondView,
    CollaborationTeamInviteView,
    CollaborationTeamLeaveView,
    OnboardingView,
    ScheduleConfigView,
    SetActiveTeamView,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")

urlpatterns = [
    path("", include(router.urls)),
    path("users/me/update/", UserSelfUpdateView.as_view(), name="user-self-update"),
    path(
        "users/me/delete-account/",
        UserAccountDeletionView.as_view(),
        name="user-delete-account",
    ),
    path("set-active-team/", SetActiveTeamView.as_view(), name="set-active-team"),
    path(
        "collaboration-teams/create/",
        CollaborationTeamCreateView.as_view(),
        name="create-collaboration-team",
    ),
    path(
        "collaboration-teams/invite/",
        CollaborationTeamInviteView.as_view(),
        name="invite-collaboration-team-member",
    ),
    path(
        "collaboration-teams/invitations/",
        CollaborationTeamInvitationListView.as_view(),
        name="list-collaboration-team-invitations",
    ),
    path(
        "collaboration-teams/invitations/<int:invitation_id>/respond/",
        CollaborationTeamInvitationRespondView.as_view(),
        name="respond-collaboration-team-invitation",
    ),
    path(
        "collaboration-teams/leave/",
        CollaborationTeamLeaveView.as_view(),
        name="leave-collaboration-team",
    ),
    # Authentication
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("signup/", UserViewSet.as_view({"post": "create"}), name="signup"),
    # Onboarding and schedule config
    path("onboarding/", OnboardingView.as_view(), name="onboarding"),
    path("schedule-config/", ScheduleConfigView.as_view(), name="schedule-config"),
]
