"""
Reusable test helpers for DRF API tests.
Provides a mixin that creates and authenticates a default admin user with a team.
"""

from user.models import CollaborationTeam, User


class AuthenticatedAdminAPIMixin:
    """Helper to create and authenticate a default API user with a team in tests."""

    @staticmethod
    def create_user(
        *,
        email,
        given_name="Api",
        family_name="Tester",
        password="StrongPassword123!",
    ):
        """Create and return a new User instance with the given credentials.
        Input: email - unique email; given_name, family_name - name parts; password - raw password
        Output: saved User instance
        """
        return User.objects.create_user(
            email=email,
            password=password,
            given_name=given_name,
            family_name=family_name,
        )

    def authenticate_admin(self, *, email_prefix="api"):
        """Create a user with a team and force-authenticate the test client.
        Input: email_prefix - prefix used for the email and team name
        Output: None; sets self.user, self.team, and authenticates self.client as side effects
        """
        self.user = self.create_user(email=f"{email_prefix}@test.com")
        self.team = CollaborationTeam.objects.create(name=f"{email_prefix} team")
        self.team.members.add(self.user)
        self.user.active_team = self.team
        self.user.save(update_fields=["active_team"])
        self.client.force_authenticate(self.user)

    def create_isolated_user(self, *, email_prefix):
        """Create a user with their own team, fully isolated from self.team.
        Input: email_prefix - prefix used for the email and team name
        Output: tuple of (user, team), both persisted and linked to each other
        """
        user = self.create_user(email=f"{email_prefix}@test.com")
        team = CollaborationTeam.objects.create(name=f"{email_prefix} team")
        team.members.add(user)
        user.active_team = team
        user.save(update_fields=["active_team"])
        return user, team
