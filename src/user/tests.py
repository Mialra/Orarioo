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
from user.models import RoleChoices, User


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
        director_user = User.objects.create_user(
            email="director@test.com",
            given_name="Director",
            password="Pass123!",
            role=RoleChoices.DIRECTOR,
        )

        self.assertTrue(admin_user.is_administrator())
        self.assertFalse(director_user.is_administrator())
        self.assertTrue(director_user.is_director())


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
            "role": "director",
        }

    def test_signup_success(self):
        response = self.client.post(self.signup_url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user", response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.user_data["email"])

    def test_signup_duplicate_email(self):
        self.client.post(self.signup_url, self.user_data, format="json")
        response = self.client.post(self.signup_url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_password_mismatch(self):
        invalid_data = self.user_data.copy()
        invalid_data["password_confirm"] = "AnotherPassword123!"

        response = self.client.post(self.signup_url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

        self.director = User.objects.create_user(
            email="director@test.com",
            password="Dir123!",
            given_name="Director",
            role=RoleChoices.DIRECTOR,
        )

    def test_get_own_profile(self):
        self.client.force_authenticate(user=self.director)

        response = self.client.get(reverse("user-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.director.email)

    def test_list_users_as_admin(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_users_as_director_forbidden(self):
        self.client.force_authenticate(user=self.director)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_password(self):
        self.client.force_authenticate(user=self.director)

        payload = {
            "current_password": "Dir123!",
            "new_password": "NewPassword123!",
            "password_confirm": "NewPassword123!",
        }

        response = self.client.post(
            reverse("user-change-password"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.director.refresh_from_db()
        self.assertTrue(self.director.check_password("NewPassword123!"))

    def test_change_password_with_wrong_current_password(self):
        self.client.force_authenticate(user=self.director)

        payload = {
            "current_password": "WrongPassword!",
            "new_password": "NewPassword123!",
            "password_confirm": "NewPassword123!",
        }

        response = self.client.post(
            reverse("user-change-password"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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

        self.director_1 = User.objects.create_user(
            email="director1@test.com",
            password="Dir123!",
            given_name="Director",
            family_name="One",
            role=RoleChoices.DIRECTOR,
        )

        self.director_2 = User.objects.create_user(
            email="director2@test.com",
            password="Dir123!",
            given_name="Director",
            family_name="Two",
            role=RoleChoices.DIRECTOR,
        )

    def test_director_cannot_view_other_profiles(self):
        self.client.force_authenticate(user=self.director_1)

        response = self.client.get(
            reverse("user-detail", kwargs={"pk": self.director_2.pk})
        )

        self.assertIn(
            response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )

    def test_admin_can_view_any_profile(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            reverse("user-detail", kwargs={"pk": self.director_1.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_director_cannot_update_other_users(self):
        self.client.force_authenticate(user=self.director_1)

        response = self.client.patch(
            reverse("user-detail", kwargs={"pk": self.director_2.pk}),
            {"given_name": "Modified"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_users(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("user-detail", kwargs={"pk": self.director_1.pk}),
            {"given_name": "Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.director_1.refresh_from_db()
        self.assertEqual(self.director_1.given_name, "Updated")
