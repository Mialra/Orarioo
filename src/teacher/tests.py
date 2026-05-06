from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.test_utils import AuthenticatedAdminAPIMixin
from teacher.models import Teacher


class TeacherApiTests(AuthenticatedAdminAPIMixin, APITestCase):
    def setUp(self):
        self.authenticate_admin(email_prefix="teacher-api")

    def test_create_teacher(self):
        payload = {
            "name": "Ana Perez",
            "max_weekly_hours": 20,
            "working_hours": 12,
        }

        response = self.client.post(reverse("teacher-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Teacher.objects.count(), 1)
        self.assertEqual(Teacher.objects.first().team, self.team)

    def test_list_and_retrieve_teacher(self):
        teacher = Teacher.objects.create(
            name="Carlos Gomez",
            max_weekly_hours=18,
            working_hours=10,
            team=self.team,
        )

        list_response = self.client.get(reverse("teacher-list"))
        detail_response = self.client.get(reverse("teacher-detail", args=[teacher.id]))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["name"], "Carlos Gomez")

    def test_update_teacher(self):
        teacher = Teacher.objects.create(
            name="Laura Ruiz",
            max_weekly_hours=22,
            working_hours=15,
            team=self.team,
        )

        payload = {
            "name": "Laura Ruiz Updated",
            "max_weekly_hours": 24,
            "working_hours": 18,
        }

        response = self.client.put(
            reverse("teacher-detail", args=[teacher.id]), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher.refresh_from_db()
        self.assertEqual(teacher.name, "Laura Ruiz Updated")
        self.assertEqual(teacher.max_weekly_hours, 24)

    def test_delete_teacher(self):
        teacher = Teacher.objects.create(
            name="Marta Lopez",
            max_weekly_hours=20,
            working_hours=10,
            team=self.team,
        )

        response = self.client.delete(reverse("teacher-detail", args=[teacher.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Teacher.objects.filter(id=teacher.id).exists())

    def test_reject_if_working_hours_exceeds_max_weekly_hours(self):
        payload = {
            "name": "Invalid Teacher",
            "max_weekly_hours": 10,
            "working_hours": 12,
        }

        response = self.client.post(reverse("teacher-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("working_hours", response.data)

    def test_reject_case_insensitive_duplicate_name(self):
        Teacher.objects.create(
            name="Pedro",
            max_weekly_hours=20,
            working_hours=10,
            team=self.team,
        )

        payload = {
            "name": "pedro",
            "max_weekly_hours": 18,
            "working_hours": 8,
        }
        response = self.client.post(reverse("teacher-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_allow_same_name_in_different_team(self):
        Teacher.objects.create(
            name="Laura",
            max_weekly_hours=20,
            working_hours=10,
            team=self.team,
        )
        other_user, other_team = self.create_isolated_user(
            email_prefix="teacher-api-other"
        )
        self.client.force_authenticate(other_user)

        response = self.client.post(
            reverse("teacher-list"),
            {
                "name": "laura",
                "max_weekly_hours": 18,
                "working_hours": 8,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Teacher.objects.filter(name__iexact="Laura").count(), 2)
        self.assertTrue(
            Teacher.objects.filter(name__iexact="Laura", team=other_team).exists()
        )

    def test_list_summary_count_and_options_are_team_scoped(self):
        Teacher.objects.create(
            name="Ana Perez",
            max_weekly_hours=20,
            working_hours=10,
            team=self.team,
        )
        Teacher.objects.create(
            name="Carlos Gomez",
            max_weekly_hours=18,
            working_hours=12,
            team=self.team,
        )
        _, isolated_team = self.create_isolated_user(email_prefix="teacher-summary")
        Teacher.objects.create(
            name="Fuera de equipo",
            max_weekly_hours=16,
            working_hours=8,
            team=isolated_team,
        )

        count_response = self.client.get(reverse("teacher-list") + "?summary=count")
        options_response = self.client.get(reverse("teacher-list") + "?summary=options")

        self.assertEqual(count_response.status_code, status.HTTP_200_OK)
        self.assertEqual(count_response.data, {"count": 2})
        self.assertEqual(options_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(options_response.data), 2)
        self.assertEqual(
            {item["name"] for item in options_response.data},
            {"Ana Perez", "Carlos Gomez"},
        )
        self.assertTrue(
            all(set(item.keys()) == {"id", "name"} for item in options_response.data)
        )
