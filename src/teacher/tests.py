from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from teacher.models import Teacher
from user.models import RoleChoices, User


class TeacherApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="teacher-api@test.com",
            password="StrongPassword123!",
            given_name="Api",
            family_name="Tester",
            role=RoleChoices.ADMINISTRATOR,
        )
        self.client.force_authenticate(self.user)

    def test_create_teacher(self):
        payload = {
            "name": "Ana Perez",
            "max_weekly_hours": 20,
            "working_hours": 12,
            "preferences": "Morning",
            "availability": "Mon-Fri 08:00-14:00",
            "unavailability": "Wed 10:00-11:00",
        }

        response = self.client.post(reverse("teacher-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Teacher.objects.count(), 1)

    def test_list_and_retrieve_teacher(self):
        teacher = Teacher.objects.create(
            name="Carlos Gomez",
            max_weekly_hours=18,
            working_hours=10,
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
        )

        payload = {
            "name": "Laura Ruiz Updated",
            "max_weekly_hours": 24,
            "working_hours": 18,
            "preferences": "Afternoon",
            "availability": "Mon-Fri 12:00-18:00",
            "unavailability": "",
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
