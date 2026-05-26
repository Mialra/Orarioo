"""Tests for user, authentication and collaboration-team flows."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from auditableEntity.models import AuditEntry
from classroom.models import Classroom
from group.models import EducationalStage as GroupEducationalStage
from group.models import Group
from schedule.models import Schedule
from subject.models import Subject
from teacher.models import Teacher
from user.admin import UserAdmin
from user.models import (CollaborationTeam, CollaborationTeamInvitation,
                         CollaborationTeamInvitationStatus, User,
                         UserDataExportLog)


class UserModelTests(TestCase):
    """Tests for the User model."""

    def setUp(self):
        self.user_data = {
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
            "password": "TestPassword123!",
        }

    def test_create_user(self):
        user = User.objects.create_user(**self.user_data)

        self.assertEqual(user.email, self.user_data["email"])
        self.assertEqual(user.name, self.user_data["given_name"])
        self.assertEqual(user.given_name, self.user_data["given_name"])
        self.assertTrue(user.check_password(self.user_data["password"]))
        self.assertTrue(user.is_enabled)

    def test_password_is_stored_hashed_not_plaintext(self):
        raw_password = self.user_data["password"]
        user = User.objects.create_user(**self.user_data)

        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.password)
        self.assertIn("$", user.password)
        self.assertTrue(user.check_password(raw_password))

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
            given_name="Admin",
        )

        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)


class UserAdminNotificationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_site = AdminSite()
        self.user_admin = UserAdmin(User, self.admin_site)
        self.superuser = User.objects.create_superuser(
            email="root@test.com",
            password="Admin123!",
            given_name="Root",
        )

    def test_save_model_sends_lockout_email_when_disabling_user(self):
        target = User.objects.create_user(
            email="target@test.com",
            password="Target123!",
            given_name="Target",
            is_enabled=True,
        )
        request = self.factory.post("/admin/user/user/{}/change/".format(target.pk))
        request.user = self.superuser

        target.is_enabled = False

        with patch("user.admin.send_security_email", return_value=True) as mocked_send:
            with patch.object(self.user_admin, "message_user"):
                self.user_admin.save_model(request, target, form=None, change=True)

        mocked_send.assert_called_once()
        kwargs = mocked_send.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["target@test.com"])
        self.assertEqual(
            kwargs["html_message"]["template"],
            "emails/security/account_lockout.html",
        )

    def test_admin_action_sends_breach_notification_to_all_enabled_users(self):
        enabled_1 = User.objects.create_user(
            email="enabled1@test.com",
            password="Enabled123!",
            given_name="Enabled1",
            is_enabled=True,
        )
        User.objects.create_user(
            email="enabled2@test.com",
            password="Enabled123!",
            given_name="Enabled2",
            is_enabled=True,
        )
        User.objects.create_user(
            email="disabled@test.com",
            password="Disabled123!",
            given_name="Disabled",
            is_enabled=False,
        )

        request = self.factory.post("/admin/user/user/")
        request.user = self.superuser
        queryset = User.objects.filter(pk=enabled_1.pk)

        with patch("user.admin.send_security_email", return_value=True) as mocked_send:
            with patch.object(self.user_admin, "message_user"):
                self.user_admin.send_security_breach_notification(request, queryset)

        mocked_send.assert_called_once()
        kwargs = mocked_send.call_args.kwargs
        recipients = set(kwargs["recipient_list"])
        self.assertEqual(
            recipients, {"enabled1@test.com", "enabled2@test.com", "root@test.com"}
        )
        self.assertEqual(
            kwargs["html_message"]["template"],
            "emails/security/security_breach.html",
        )


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
            "privacy_policy_accepted": True,
            "terms_conditions_accepted": True,
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

    def test_signup_rejects_password_without_number(self):
        invalid_data = self.user_data.copy()
        invalid_data["email"] = "nonumber@example.com"
        invalid_data["password"] = "PasswordOnly"
        invalid_data["password_confirm"] = "PasswordOnly"

        response = self.client.post(self.signup_url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_signup_rejects_email_exceeding_max_length(self):
        invalid_data = self.user_data.copy()
        # Create an email much longer than typical to ensure rejection
        invalid_data["email"] = "a" * 200 + "@example.com"

        response = self.client.post(self.signup_url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_signup_accepts_email_within_max_length(self):
        valid_data = self.user_data.copy()
        valid_data["email"] = "a" * 87 + "@example.com"

        response = self.client.post(self.signup_url, valid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_signup_requires_privacy_policy_acceptance(self):
        invalid_data = self.user_data.copy()
        invalid_data["privacy_policy_accepted"] = False

        response = self.client.post(self.signup_url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("privacy_policy_accepted", response.data)

    def test_signup_requires_terms_conditions_acceptance(self):
        invalid_data = self.user_data.copy()
        invalid_data["terms_conditions_accepted"] = False

        response = self.client.post(self.signup_url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("terms_conditions_accepted", response.data)

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
    """Tests for user endpoints and team scoping."""

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="Admin123!",
            given_name="Admin",
        )

        self.direccion = User.objects.create_user(
            email="direccion@test.com",
            password="Dir123!",
            given_name="Direccion",
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

    def test_list_users_returns_active_team_members(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_users_is_scoped_to_active_team(self):
        outsider = User.objects.create_user(
            email="outsider@test.com",
            password="Outsider123!",
            given_name="Outsider",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row["id"] for row in response.data["results"]}
        self.assertNotIn(outsider.id, returned_ids)

    def test_retrieve_user_in_same_team(self):
        self.client.force_authenticate(user=self.direccion)
        response = self.client.get(reverse("user-detail", kwargs={"pk": self.admin.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_user_outside_team_not_found(self):
        outsider = User.objects.create_user(
            email="outsider2@test.com",
            password="Outsider123!",
            given_name="Outsider2",
        )
        self.client.force_authenticate(user=self.direccion)
        response = self.client.get(reverse("user-detail", kwargs={"pk": outsider.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_is_not_allowed(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(
            reverse("user-detail", kwargs={"pk": self.direccion.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

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


class AccountDeletionTests(APITestCase):
    """Tests for irreversible self-service account deletion."""

    def setUp(self):
        self.client = APIClient()

        self.password = "DeleteMe123!"
        self.user = User.objects.create_user(
            email="delete-me@test.com",
            password=self.password,
            given_name="Delete",
            family_name="Me",
        )

        self.team = CollaborationTeam.objects.create(name="Equipo RGPD")
        self.team.members.add(self.user)
        self.user.active_team = self.team
        self.user.save(update_fields=["active_team"])

        self.teacher = Teacher.objects.create(
            name="Profesor RGPD",
            team=self.team,
            max_weekly_hours=20,
            time_preferences={},
        )
        self.classroom = Classroom.objects.create(
            name="Aula RGPD",
            team=self.team,
        )
        self.group = Group.objects.create(
            name="Grupo RGPD",
            team=self.team,
            stage=GroupEducationalStage.PRIMARY,
        )
        self.subject = Subject.objects.create(
            name="Asignatura RGPD",
            team=self.team,
            weekly_hours=2,
            teacher=self.teacher,
            group=self.group,
            classroom=self.classroom,
        )
        now = timezone.now()
        self.schedule = Schedule.objects.create(
            name="Horario RGPD",
            team=self.team,
            teacher=self.teacher,
            classroom=self.classroom,
            group=self.group,
            subject=self.subject,
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        self.schedule.users.add(self.user)

        for entity in [
            self.teacher,
            self.classroom,
            self.group,
            self.subject,
            self.schedule,
        ]:
            entity.created_by = self.user.email
            entity.updated_by = self.user.email
            entity.save(update_fields=["created_by", "updated_by"])

        self.login_url = reverse("token_obtain_pair")
        self.delete_url = reverse("user-delete-account")
        self.me_url = reverse("user-me")
        self.profile_url = reverse("profile")

    def authenticate(self):
        response = self.client.post(
            self.login_url,
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_profile_page_exposes_account_deletion_ui(self):
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Eliminar cuenta")
        self.assertContains(response, "profileDeleteAccountModal")
        self.assertContains(response, "correo electrónico")

    def test_delete_account_rejects_invalid_confirmation_text(self):
        self.authenticate()

        response = self.client.post(
            self.delete_url,
            {
                "confirmation_text": "BORRAR",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirmation_text", response.data)

    def test_delete_account_anonymizes_user_and_related_records(self):
        self.authenticate()

        response = self.client.post(
            self.delete_url,
            {
                "confirmation_text": self.user.email,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()

        self.assertEqual(self.user.name, "Usuario eliminado")
        self.assertEqual(self.user.family_name, "")
        self.assertTrue(self.user.email.startswith("deleted-"))
        self.assertIsNone(self.user.password)
        self.assertIsNotNone(self.user.deleted_at)
        self.assertFalse(self.user.is_enabled)
        self.assertIsNone(self.user.active_team)
        self.assertFalse(self.team.members.filter(pk=self.user.pk).exists())
        self.assertFalse(self.schedule.users.filter(pk=self.user.pk).exists())
        self.assertFalse(UserDataExportLog.objects.filter(user=self.user).exists())

        self.teacher.refresh_from_db()
        self.classroom.refresh_from_db()
        self.group.refresh_from_db()
        self.subject.refresh_from_db()
        self.schedule.refresh_from_db()

        self.assertEqual(self.teacher.created_by, self.user.email)
        self.assertEqual(self.teacher.updated_by, self.user.email)
        self.assertEqual(self.classroom.created_by, self.user.email)
        self.assertEqual(self.classroom.updated_by, self.user.email)
        self.assertEqual(self.group.created_by, self.user.email)
        self.assertEqual(self.group.updated_by, self.user.email)
        self.assertEqual(self.subject.created_by, self.user.email)
        self.assertEqual(self.subject.updated_by, self.user.email)
        self.assertEqual(self.schedule.created_by, self.user.email)
        self.assertEqual(self.schedule.updated_by, self.user.email)

        self.assertTrue(
            AuditEntry.objects.filter(
                entity_type="user",
                entity_id=self.user.pk,
                action_type="DELETE",
            ).exists()
        )

    def test_deleted_account_cannot_keep_using_old_jwt(self):
        self.authenticate()

        delete_response = self.client.post(
            self.delete_url,
            {
                "confirmation_text": self.user.email,
            },
            format="json",
        )
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)

        follow_up = self.client.get(self.me_url)
        self.assertEqual(follow_up.status_code, status.HTTP_401_UNAUTHORIZED)


class CollaborationTeamApiTests(APITestCase):
    """Tests for collaboration team creation/invitations/membership flows."""

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin-team@test.com",
            password="Admin123!",
            given_name="Admin",
        )

        self.member = User.objects.create_user(
            email="member@test.com",
            password="Member123!",
            given_name="Member",
        )

        self.team = CollaborationTeam.objects.create(name="Equipo Inicial")
        self.team.members.add(self.admin, self.member)
        self.admin.active_team = self.team
        self.member.active_team = self.team
        self.admin.save(update_fields=["active_team"])
        self.member.save(update_fields=["active_team"])

    def test_create_collaboration_team_assigns_creator_as_member_and_active_team(self):
        solo_user = User.objects.create_user(
            email="solo@test.com",
            password="Solo123!",
            given_name="Solo",
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
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("invite-collaboration-team-member"),
            {"email": invited_user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invited_user.refresh_from_db()
        self.assertFalse(
            invited_user.collaboration_teams.filter(id=self.team.id).exists()
        )
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
            {"email": self.member.email},
            format="json",
        )

        # 409 Conflict: user already in team
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_invite_rejects_duplicate_pending_invitation(self):
        invited_user = User.objects.create_user(
            email="pending-invitee@test.com",
            password="Invitee123!",
            given_name="Invitado",
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

        # 409 Conflict: pending invitation already exists
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_list_pending_invitations_for_current_user(self):
        CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.member,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(reverse("list-collaboration-team-invitations"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_count"], 1)
        self.assertEqual(response.data["count"], 1)

    def test_list_invitations_can_filter_pending_status(self):
        CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.member,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )
        CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.member,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.ACCEPTED,
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(
            reverse("list-collaboration-team-invitations") + "?status=pending"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["pending_count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["status"],
            CollaborationTeamInvitationStatus.PENDING,
        )

    def test_list_invitations_can_return_summary_count(self):
        CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.member,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )
        CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.member,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.ACCEPTED,
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(
            reverse("list-collaboration-team-invitations") + "?summary=count"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"count": 2, "pending_count": 1})

    def test_accept_invitation_adds_membership(self):
        invitation = CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.member,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )
        self.team.members.remove(self.member)

        self.client.force_authenticate(user=self.member)
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
        self.assertTrue(self.team.members.filter(id=self.member.id).exists())

    def test_reject_invitation_marks_rejected(self):
        invitation = CollaborationTeamInvitation.objects.create(
            team=self.team,
            invited_user=self.member,
            invited_by=self.admin,
            status=CollaborationTeamInvitationStatus.PENDING,
        )
        self.team.members.remove(self.member)

        self.client.force_authenticate(user=self.member)
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
        self.assertFalse(self.team.members.filter(id=self.member.id).exists())

    def test_leave_team_removes_membership(self):
        second_team = CollaborationTeam.objects.create(name="Equipo Segundo")
        second_team.members.add(self.member)
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            reverse("leave-collaboration-team"),
            {"team_id": self.team.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.team.members.filter(id=self.member.id).exists())


class ScheduleConfigApiTests(APITestCase):
    """Tests for onboarding and schedule-config stage metadata."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="tramos@test.com",
            password="Tramos123!",
            given_name="Tramos",
        )
        self.team = CollaborationTeam.objects.create(name="Equipo Tramos")
        self.team.members.add(self.user)
        self.user.active_team = self.team
        self.user.save(update_fields=["active_team"])
        self.client.force_authenticate(user=self.user)
        self.schedule_config_url = "/api/schedule-config/"
        self.onboarding_url = "/api/onboarding/"

    def test_get_schedule_config_returns_empty_config_when_no_stages_exist(self):
        response = self.client.get(self.schedule_config_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("stage_colors", response.data)
        self.assertEqual(response.data["schedule_config"], {})

    def test_put_schedule_config_rejects_invalid_color(self):
        payload = {
            "schedule_config": {
                "PRIMARY": {
                    "label": "Primaria",
                    "color": "turquoise",
                    "start_time": "09:00",
                    "end_time": "14:00",
                    "breaks": [],
                    "session_duration": 60,
                }
            }
        }

        response = self.client.put(self.schedule_config_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("schedule_config", response.data)

    def test_put_schedule_config_persists_color_and_stage_colors_map(self):
        payload = {
            "schedule_config": {
                "PRIMARY": {
                    "label": "Primaria",
                    "color": "pink",
                    "start_time": "09:00",
                    "end_time": "14:00",
                    "breaks": [],
                    "session_duration": 60,
                }
            }
        }

        response = self.client.put(self.schedule_config_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.team.refresh_from_db()
        self.assertEqual(self.team.schedule_config["PRIMARY"]["color"], "pink")
        self.assertEqual(response.data["stage_colors"]["PRIMARY"], "pink")

    def test_put_schedule_config_rejects_non_sixty_minute_session_duration(self):
        payload = {
            "schedule_config": {
                "PRIMARY": {
                    "label": "Primaria",
                    "color": "blue",
                    "start_time": "09:00",
                    "end_time": "14:00",
                    "breaks": [],
                    "session_duration": 45,
                }
            }
        }

        response = self.client.put(self.schedule_config_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("schedule_config", response.data)

    def test_put_schedule_config_returns_code_for_break_outside_stage_range(self):
        payload = {
            "schedule_config": {
                "PRIMARY": {
                    "label": "Primaria",
                    "color": "blue",
                    "start_time": "09:00",
                    "end_time": "14:00",
                    "breaks": [{"start": "08:30", "end": "09:15"}],
                    "session_duration": 60,
                }
            }
        }

        response = self.client.put(self.schedule_config_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_entry = response.data["errors"]["schedule_config"][0]
        self.assertEqual(error_entry["code"], "BREAK_OUTSIDE_STAGE_RANGE")
        self.assertEqual(
            error_entry["message"],
            "El recreo debe estar dentro de la hora de entrada y salida de la etapa.",
        )

    def test_onboarding_applies_default_stage_color_when_missing(self):
        onboarding_user = User.objects.create_user(
            email="nuevo-centro@test.com",
            password="NuevoCentro123!",
            given_name="Centro",
        )
        self.client.force_authenticate(user=onboarding_user)

        response = self.client.post(
            self.onboarding_url,
            {
                "team_name": "Centro Nuevo",
                "schedule_config": {
                    "PRIMARY": {
                        "label": "Primaria",
                        "start_time": "09:00",
                        "end_time": "14:00",
                        "breaks": [],
                        "session_duration": 60,
                    }
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        onboarding_user.refresh_from_db()
        self.assertEqual(
            onboarding_user.active_team.schedule_config["PRIMARY"]["color"],
            "blue",
        )

    def test_onboarding_allows_empty_schedule_config(self):
        onboarding_user = User.objects.create_user(
            email="centro-sin-tramos@test.com",
            password="NuevoCentro123!",
            given_name="Centro",
        )
        self.client.force_authenticate(user=onboarding_user)

        response = self.client.post(
            self.onboarding_url,
            {
                "team_name": "Centro Sin Tramos",
                "schedule_config": {},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        onboarding_user.refresh_from_db()
        self.assertEqual(onboarding_user.active_team.name, "Centro Sin Tramos")
        self.assertEqual(onboarding_user.active_team.schedule_config, {})

    def test_put_schedule_config_blocks_deleting_stage_in_use(self):
        self.team.schedule_config = {
            "PRIMARY": {
                "label": "Primaria",
                "color": "blue",
                "start_time": "09:00",
                "end_time": "14:00",
                "breaks": [],
                "session_duration": 60,
            },
            "SECONDARY": {
                "label": "ESO",
                "color": "orange",
                "start_time": "08:00",
                "end_time": "14:30",
                "breaks": [],
                "session_duration": 60,
            },
        }
        self.team.save(update_fields=["schedule_config"])
        Group.objects.create(
            name="1A",
            team=self.team,
            stage=GroupEducationalStage.PRIMARY,
        )

        payload = {
            "schedule_config": {
                "SECONDARY": {
                    "label": "ESO",
                    "color": "orange",
                    "start_time": "08:00",
                    "end_time": "14:30",
                    "breaks": [],
                    "session_duration": 60,
                }
            }
        }

        response = self.client.put(self.schedule_config_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("schedule_config", response.data)
        self.assertIn("No se puede eliminar una etapa", response.data["detail"])


class PermissionsTests(APITestCase):
    """Tests for access behavior under team scoping and read-only user API."""

    def setUp(self):
        self.client = APIClient()

        self.user_1 = User.objects.create_user(
            email="user1@test.com",
            password="User123!",
            given_name="User",
            family_name="One",
        )

        self.user_2 = User.objects.create_user(
            email="user2@test.com",
            password="User123!",
            given_name="User",
            family_name="Two",
        )

        self.outside = User.objects.create_user(
            email="outside@test.com",
            password="User123!",
            given_name="Outside",
        )

        self.team = CollaborationTeam.objects.create(name="Equipo Permisos")
        self.team.members.add(self.user_1, self.user_2)
        self.user_1.active_team = self.team
        self.user_2.active_team = self.team
        self.user_1.save(update_fields=["active_team"])
        self.user_2.save(update_fields=["active_team"])

    def test_same_team_user_can_view_other_profile(self):
        self.client.force_authenticate(user=self.user_1)

        response = self.client.get(
            reverse("user-detail", kwargs={"pk": self.user_2.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_outside_team_user_cannot_view_profile(self):
        self.client.force_authenticate(user=self.user_1)

        response = self.client.get(
            reverse("user-detail", kwargs={"pk": self.outside.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(
    DATA_EXPORT_RATE_LIMIT_MAX_REQUESTS=2,
    DATA_EXPORT_RATE_LIMIT_WINDOW_SECONDS=3600,
)
class DataPortabilityTests(TestCase):
    """Tests for S-08 GDPR data portability profile and export flow."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="gdpr-user@test.com",
            password="StrongPassword123!",
            given_name="Lucia",
            family_name="Martinez",
        )
        self.other_user = User.objects.create_user(
            email="other-user@test.com",
            password="StrongPassword123!",
            given_name="Carlos",
            family_name="Lopez",
        )
        self.profile_url = reverse("profile")
        self.export_url = reverse("profile-export-data")

    def _authenticate_as_user(self):
        self.client.force_authenticate(user=self.user)

    def test_profile_page_is_accessible_shell(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Eliminar cuenta")

    def test_export_requires_authentication(self):
        response = self.client.post(self.export_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_json_integrity_and_headers(self):
        self._authenticate_as_user()

        response = self.client.post(
            self.export_url,
            REMOTE_ADDR="203.0.113.7",
            HTTP_USER_AGENT="OrariooTest/1.0",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store, private")

        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("exported_at", payload["metadata"])
        self.assertIn("personal_data", payload)
        self.assertEqual(payload["personal_data"]["username"], self.user.name)
        self.assertEqual(payload["personal_data"]["family_name"], self.user.family_name)
        self.assertEqual(payload["personal_data"]["email"], self.user.email)
        self.assertIn("active_team", payload["personal_data"])
        self.assertIn("activity", payload)
        self.assertIsInstance(payload["activity"], list)

        self.assertNotIn("system_id", payload["metadata"])
        self.assertNotIn("export_version", payload["metadata"])
        self.assertNotIn("legal_reference", payload["metadata"])
        self.assertNotIn("data_subject", payload["metadata"])
        self.assertNotIn("user_data", payload)
        self.assertNotIn("name", payload["personal_data"])
        self.assertNotIn("account_created_at", payload["personal_data"])

    def test_export_does_not_include_other_user_data(self):
        self._authenticate_as_user()

        response = self.client.post(
            self.export_url,
        )
        payload = json.loads(response.content.decode("utf-8"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(payload["personal_data"]["email"], self.other_user.email)
        self.assertEqual(payload["personal_data"]["email"], self.user.email)

    def test_rate_limiting_blocks_excessive_requests(self):
        self._authenticate_as_user()

        first = self.client.post(self.export_url)
        second = self.client.post(self.export_url)
        third = self.client.post(self.export_url)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(third.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", third)

    def test_audit_log_is_created_with_user_time(self):
        self._authenticate_as_user()

        response = self.client.post(self.export_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = UserDataExportLog.objects.filter(user=self.user).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.outcome, UserDataExportLog.Outcome.SUCCESS)
        self.assertIsNotNone(log.created_at)

    def test_get_on_export_endpoint_is_not_allowed(self):
        self._authenticate_as_user()
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
