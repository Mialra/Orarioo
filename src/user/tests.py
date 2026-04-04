"""
Tests for the Orarioo user backend.

This file contains tests to verify authentication,
permissions, and user management behavior.

Run with:
    python manage.py test user
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from namedEntity.models import NamedEntity
from user.models import (
    CollaborationTeam,
    CollaborationTeamInvitation,
    CollaborationTeamInvitationStatus,
    RoleChoices,
    User,
)


class UserModelTests(TestCase):
    """Tests for the User model."""

    def setUp(self):
        self.user_data = {
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
            "password": "TestPassword123!",
            "role": RoleChoices.ADMINISTRATOR,
        }

    def test_create_user(self):
        """Creates a regular user successfully."""
        user = User.objects.create_user(**self.user_data)

        self.assertEqual(user.email, self.user_data["email"])
        self.assertEqual(user.name, self.user_data["given_name"])
        self.assertEqual(user.given_name, self.user_data["given_name"])
        self.assertTrue(user.check_password(self.user_data["password"]))
        self.assertTrue(user.is_enabled)

    def test_password_is_stored_hashed_not_plaintext(self):
        """Password must be stored hashed and never equal to the raw input."""
        raw_password = self.user_data["password"]
        user = User.objects.create_user(**self.user_data)

        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.password)
        self.assertIn("$", user.password)
        self.assertTrue(user.check_password(raw_password))

    def test_user_inherits_named_entity(self):
        self.assertTrue(issubclass(User, NamedEntity))

    def test_create_superuser(self):
        """Creates a superuser successfully."""
        superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
            given_name="Admin",
        )

        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)
        self.assertEqual(superuser.role, RoleChoices.ADMINISTRATOR)

    def test_string_representation(self):
        """Uses first and last name in string representation."""
        user = User.objects.create_user(**self.user_data)
        expected = f"{user.given_name} {user.family_name} ({user.email})"

        self.assertEqual(str(user), expected)

    def test_role_helpers(self):
        """Checks role helper methods."""
        admin_user = User.objects.create_user(
            email="admin@test.com",
            given_name="Admin",
            password="Pass123!",
            role=RoleChoices.ADMINISTRATOR,
        )
        direccion_user = User.objects.create_user(
            email="direccion@test.com",
            given_name="Direccion",
            password="Pass123!",
            role=RoleChoices.DIRECCION,
        )

        self.assertTrue(admin_user.is_administrator())
        self.assertFalse(direccion_user.is_administrator())
        self.assertTrue(direccion_user.is_direccion())

    def test_only_expected_roles_exist(self):
        self.assertEqual(set(RoleChoices.values), {"administrator", "direccion"})


class AuthenticationApiTests(APITestCase):
    """Tests for authentication endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.signup_url = reverse("signup")
        self.login_url = reverse("token_obtain_pair")

        self.user_data = {
            "given_name": "Test",
            "family_name": "User",
            "email": "test@example.com",
            "password": "TestPassword123!",
            "password_confirm": "TestPassword123!",
            "role": "direccion",
        }

    def test_signup_success(self):
        response = self.client.post(self.signup_url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user", response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.user_data["email"])
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_confirm", response.data)
        self.assertNotIn("password", response.data["user"])

    def test_signup_duplicate_email(self):
        self.client.post(self.signup_url, self.user_data, format="json")
        response = self.client.post(self.signup_url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_password_mismatch(self):
        invalid_data = self.user_data.copy()
        invalid_data["password_confirm"] = "AnotherPassword123!"

        response = self.client.post(self.signup_url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_assigns_administrator_role_when_requested(self):
        admin_payload = self.user_data.copy()
        admin_payload["email"] = "admin-signup@test.com"
        admin_payload["role"] = "administrator"

        response = self.client.post(self.signup_url, admin_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email=admin_payload["email"])
        self.assertEqual(created_user.role, RoleChoices.ADMINISTRATOR)

    def test_signup_assigns_direccion_role_when_requested(self):
        direccion_payload = self.user_data.copy()
        direccion_payload["email"] = "direccion-signup@test.com"
        direccion_payload["role"] = "direccion"

        response = self.client.post(self.signup_url, direccion_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email=direccion_payload["email"])
        self.assertEqual(created_user.role, RoleChoices.DIRECCION)

    def test_signup_defaults_to_direccion_when_role_missing(self):
        payload = self.user_data.copy()
        payload["email"] = "default-role@test.com"
        payload.pop("role", None)

        response = self.client.post(self.signup_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email=payload["email"])
        self.assertEqual(created_user.role, RoleChoices.DIRECCION)

    def test_signup_rejects_invalid_role_value(self):
        invalid_role_payload = self.user_data.copy()
        invalid_role_payload["email"] = "invalid-role@test.com"
        invalid_role_payload["role"] = "administrador"

        response = self.client.post(
            self.signup_url,
            invalid_role_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_login_success(self):
        User.objects.create_user(
            email=self.user_data["email"],
            password=self.user_data["password"],
            given_name=self.user_data["given_name"],
        )

        login_data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"],
        }
        response = self.client.post(self.login_url, login_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", response.data["user"])

    def test_login_invalid_credentials(self):
        User.objects.create_user(
            email=self.user_data["email"],
            password=self.user_data["password"],
            given_name=self.user_data["given_name"],
        )

        login_data = {
            "email": self.user_data["email"],
            "password": "WrongPassword123!",
        }
        response = self.client.post(self.login_url, login_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user(self):
        User.objects.create_user(
            email=self.user_data["email"],
            password=self.user_data["password"],
            given_name=self.user_data["given_name"],
            is_enabled=False,
        )

        login_data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"],
        }
        response = self.client.post(self.login_url, login_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserApiTests(APITestCase):
    """Tests for user management endpoints."""

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="Admin123!",
            given_name="Admin",
            role=RoleChoices.ADMINISTRATOR,
        )

        self.direccion = User.objects.create_user(
            email="direccion@test.com",
            password="Dir123!",
            given_name="Direccion",
            role=RoleChoices.DIRECCION,
        )
        self.team = CollaborationTeam.objects.create(name="Equipo API")
        self.team.members.add(self.admin, self.direccion)
        self.admin.active_team = self.team
        self.direccion.active_team = self.team
        self.admin.save(update_fields=["active_team"])
        self.direccion.save(update_fields=["active_team"])

    def test_get_own_profile(self):
        self.client.force_authenticate(user=self.direccion)

        response = self.client.get(reverse("user-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.direccion.email)

    def test_list_users_as_admin(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_users_is_scoped_to_active_team(self):
        outsider = User.objects.create_user(
            email="outsider@test.com",
            password="Outsider123!",
            given_name="Outsider",
            role=RoleChoices.DIRECCION,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row["id"] for row in response.data["results"]}
        self.assertNotIn(outsider.id, returned_ids)

    def test_list_users_as_direccion_forbidden(self):
        self.client.force_authenticate(user=self.direccion)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_managed_create_user_without_login_password(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "given_name": "Nuevo",
            "family_name": "Direccion",
            "email": "nuevo-direccion@test.com",
            "role": "direccion",
            "can_login": False,
        }
        response = self.client.post(
            reverse("user-managed-create"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email="nuevo-direccion@test.com")
        self.assertFalse(created_user.has_usable_password())

    def test_managed_create_user_with_login_requires_password(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "given_name": "Nuevo",
            "family_name": "Admin",
            "email": "nuevo-admin@test.com",
            "role": "administrator",
            "can_login": True,
        }
        response = self.client.post(
            reverse("user-managed-create"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_change_password(self):
        self.client.force_authenticate(user=self.direccion)

        payload = {
            "current_password": "Dir123!",
            "new_password": "NewPassword123!",
            "password_confirm": "NewPassword123!",
        }

        response = self.client.post(
            reverse("user-change-password"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.direccion.refresh_from_db()
        self.assertTrue(self.direccion.check_password("NewPassword123!"))

    def test_change_password_with_wrong_current_password(self):
        self.client.force_authenticate(user=self.direccion)

        payload = {
            "current_password": "WrongPassword!",
            "new_password": "NewPassword123!",
            "password_confirm": "NewPassword123!",
        }

        response = self.client.post(
            reverse("user-change-password"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_active_team(self):
        second_team = CollaborationTeam.objects.create(name="Equipo Secundario")
        second_team.members.add(self.direccion)

        self.client.force_authenticate(user=self.direccion)

        response = self.client.post(
            reverse("set-active-team"),
            {"team_id": second_team.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.direccion.refresh_from_db()
        self.assertEqual(self.direccion.active_team_id, second_team.id)
        self.assertEqual(response.data["user"]["active_team"]["id"], second_team.id)

    def test_set_active_team_rejects_foreign_team(self):
        foreign_team = CollaborationTeam.objects.create(name="Equipo Externo")

        self.client.force_authenticate(user=self.direccion)

        response = self.client.post(
            reverse("set-active-team"),
            {"team_id": foreign_team.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team_id", response.data)

    def test_create_collaboration_team_assigns_creator_as_member_and_active_team(self):
        solo_user = User.objects.create_user(
            email="solo@test.com",
            password="Solo123!",
            given_name="Solo",
            role=RoleChoices.DIRECCION,
        )

        self.client.force_authenticate(user=solo_user)
        response = self.client.post(
            reverse("create-collaboration-team"),
            {"name": "Equipo Solo"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        solo_user.refresh_from_db()
        self.assertIsNotNone(solo_user.active_team_id)
        self.assertEqual(response.data["team"]["id"], solo_user.active_team_id)
        self.assertTrue(
            solo_user.collaboration_teams.filter(id=solo_user.active_team_id).exists()
        )

    def test_invite_user_to_active_team(self):
        invited_user = User.objects.create_user(
            email="invitee@test.com",
            password="Invitee123!",
            given_name="Invitado",
            role=RoleChoices.DIRECCION,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("invite-collaboration-team-member"),
            {"email": invited_user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invited_user.refresh_from_db()
        self.assertFalse(invited_user.collaboration_teams.filter(id=self.team.id).exists())
        self.assertTrue(
            CollaborationTeamInvitation.objects.filter(
                team=self.team,
                invited_user=invited_user,
                status=CollaborationTeamInvitationStatus.PENDING,
            ).exists()
        )

    def test_invite_rejects_when_user_already_in_team(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("invite-collaboration-team-member"),
            {"email": self.direccion.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_rejects_duplicate_pending_invitation(self):
        invited_user = User.objects.create_user(
            email="pending-invitee@test.com",
            password="Invitee123!",
            given_name="Invitado",
            role=RoleChoices.DIRECCION,
        )
        CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=invited_user,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("invite-collaboration-team-member"),
            {"email": invited_user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_pending_invitations_for_current_user(self):
        CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.direccion,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )

        self.client.force_authenticate(user=self.direccion)
        response = self.client.get(reverse("list-collaboration-team-invitations"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_count"], 1)
        self.assertEqual(response.data["count"], 1)

    def test_accept_invitation_adds_membership(self):
        invitation = CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.direccion,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )
        self.team.members.remove(self.direccion)

        self.client.force_authenticate(user=self.direccion)
        response = self.client.post(
            reverse(
                "respond-collaboration-team-invitation",
                kwargs={"invitation_id": invitation.id},
            ),
            {"action": "accept"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CollaborationTeamInvitationStatus.ACCEPTED)
        self.assertTrue(self.team.members.filter(id=self.direccion.id).exists())

    def test_reject_invitation_marks_rejected(self):
        invitation = CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.direccion,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )
        self.team.members.remove(self.direccion)

        self.client.force_authenticate(user=self.direccion)
        response = self.client.post(
            reverse(
                "respond-collaboration-team-invitation",
                kwargs={"invitation_id": invitation.id},
            ),
            {"action": "reject"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CollaborationTeamInvitationStatus.REJECTED)
        self.assertFalse(self.team.members.filter(id=self.direccion.id).exists())

    def test_leave_team_removes_membership(self):
        self.client.force_authenticate(user=self.direccion)
        response = self.client.post(
            reverse("leave-collaboration-team"),
            {"team_id": self.team.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.team.members.filter(id=self.direccion.id).exists())


class PermissionsTests(APITestCase):
    """Tests for permissions and access control."""

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="Admin123!",
            given_name="Admin",
            role=RoleChoices.ADMINISTRATOR,
        )

        self.direccion_1 = User.objects.create_user(
            email="direccion1@test.com",
            password="Dir123!",
            given_name="Direccion",
            family_name="One",
            role=RoleChoices.DIRECCION,
        )

        self.direccion_2 = User.objects.create_user(
            email="direccion2@test.com",
            password="Dir123!",
            given_name="Direccion",
            family_name="Two",
            role=RoleChoices.DIRECCION,
        )

        self.team = CollaborationTeam.objects.create(name="Equipo Permisos")
        self.team.members.add(self.admin, self.direccion_1, self.direccion_2)
        self.admin.active_team = self.team
        self.direccion_1.active_team = self.team
        self.direccion_2.active_team = self.team
        self.admin.save(update_fields=["active_team"])
        self.direccion_1.save(update_fields=["active_team"])
        self.direccion_2.save(update_fields=["active_team"])

    def test_direccion_cannot_view_other_profiles(self):
        self.client.force_authenticate(user=self.direccion_1)

        response = self.client.get(
            reverse("user-detail", kwargs={"pk": self.direccion_2.pk})
        )

        self.assertIn(
            response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )

    def test_admin_can_view_any_profile(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            reverse("user-detail", kwargs={"pk": self.direccion_1.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_direccion_cannot_update_other_users(self):
        self.client.force_authenticate(user=self.direccion_1)

        response = self.client.patch(
            reverse("user-detail", kwargs={"pk": self.direccion_2.pk}),
            {"given_name": "Modified"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_update_users(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("user-detail", kwargs={"pk": self.direccion_1.pk}),
            {"given_name": "Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.direccion_1.refresh_from_db()
        self.assertEqual(self.direccion_1.given_name, "Updated")
