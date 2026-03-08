from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from group.models import EducationalStage as GroupEducationalStage
from group.models import Group
from subject.models import EducationalStage, Subject, SubjectType
from teacher.models import Teacher
from user.models import RoleChoices, User


class SubjectApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="subject-api@test.com",
            password="StrongPassword123!",
            given_name="Api",
            family_name="Tester",
            role=RoleChoices.ADMINISTRATOR,
        )
        self.client.force_authenticate(self.user)

        self.teacher = Teacher.objects.create(
            name="John Doe",
            max_weekly_hours=40,
            working_hours=20,
        )
        self.group = Group.objects.create(
            name="1º ESO A",
            stage=GroupEducationalStage.SECONDARY,
        )

    def test_create_subject(self):
        payload = {
            "name": "Mathematics",
            "weekly_hours": 5,
            "duration": 1.5,
            "preferred_time_slot": "Morning",
            "stage": EducationalStage.PRIMARY,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
            "group": self.group.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Subject.objects.count(), 1)
        self.assertEqual(response.data["name"], "Mathematics")
        self.assertEqual(response.data["teacher_name"], "John Doe")

    def test_list_and_retrieve_subject(self):
        subject = Subject.objects.create(
            name="Science",
            weekly_hours=4,
            duration=1.0,
            stage=EducationalStage.SECONDARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )

        list_response = self.client.get(reverse("subject-list"))
        detail_response = self.client.get(reverse("subject-detail", args=[subject.id]))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["name"], "Science")
        self.assertEqual(detail_response.data["stage"], EducationalStage.SECONDARY)

    def test_update_subject(self):
        subject = Subject.objects.create(
            name="History",
            weekly_hours=3,
            duration=1.0,
            stage=EducationalStage.SECONDARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )

        payload = {
            "name": "History Updated",
            "weekly_hours": 4,
            "duration": 1.5,
            "preferred_time_slot": "Afternoon",
            "stage": EducationalStage.PRIMARY,
            "type": SubjectType.TC,
            "teacher": self.teacher.id,
            "group": self.group.id,
        }

        response = self.client.put(
            reverse("subject-detail", args=[subject.id]), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subject.refresh_from_db()
        self.assertEqual(subject.name, "History Updated")
        self.assertEqual(subject.weekly_hours, 4)
        self.assertEqual(subject.type, SubjectType.TC)

    def test_delete_subject(self):
        subject = Subject.objects.create(
            name="Art",
            weekly_hours=2,
            duration=1.0,
            stage=EducationalStage.PRESCHOOL,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )

        response = self.client.delete(reverse("subject-detail", args=[subject.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Subject.objects.filter(id=subject.id).exists())

    def test_reject_invalid_duration(self):
        payload = {
            "name": "Invalid Subject",
            "weekly_hours": 3,
            "duration": -1.0,
            "stage": EducationalStage.PRIMARY,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
            "group": self.group.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("duration", response.data)

    def test_reject_invalid_weekly_hours(self):
        payload = {
            "name": "Invalid Subject",
            "weekly_hours": -5,
            "duration": 1.0,
            "stage": EducationalStage.PRIMARY,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
            "group": self.group.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("weekly_hours", response.data)

    def test_subject_teacher_relationship(self):
        subject = Subject.objects.create(
            name="Physics",
            weekly_hours=4,
            duration=1.5,
            stage=EducationalStage.SECONDARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )

        self.assertEqual(subject.teacher.id, self.teacher.id)
        self.assertEqual(self.teacher.subjects.count(), 1)
        self.assertEqual(self.teacher.subjects.first().name, "Physics")

    def test_reject_missing_group(self):
        payload = {
            "name": "Sin curso",
            "weekly_hours": 3,
            "duration": 1.0,
            "stage": EducationalStage.SECONDARY,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("group", response.data)
