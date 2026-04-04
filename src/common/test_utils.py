from user.models import CollaborationTeam, RoleChoices, User


class AuthenticatedAdminAPIMixin:
    """Helper to create and authenticate a default admin API user in tests."""

    @staticmethod
    def create_user(
        *,
        email,
        role,
        given_name="Api",
        family_name="Tester",
        password="StrongPassword123!",
    ):
        return User.objects.create_user(
            email=email,
            password=password,
            given_name=given_name,
            family_name=family_name,
            role=role,
        )

    def authenticate_admin(self, *, email_prefix="api"):
        self.user = self.create_user(
            email=f"{email_prefix}@test.com",
            role=RoleChoices.ADMINISTRATOR,
        )
        self.team = CollaborationTeam.objects.create(name=f"{email_prefix} team")
        self.team.members.add(self.user)
        self.user.active_team = self.team
        self.user.save(update_fields=["active_team"])
        self.client.force_authenticate(self.user)
