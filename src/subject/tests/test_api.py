from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.stages import EducationalStage
from common.test_utils import AuthenticatedAdminAPIMixin
from group.models import EducationalStage as GroupEducationalStage
from group.models import Group
from subject.models import Subject, SubjectType
from teacher.models import Teacher


class SubjectApiTests(AuthenticatedAdminAPIMixin, APITestCase):
    def setUp(self):
        self.authenticate_admin(email_prefix="subject-api")

        self.teacher = Teacher.objects.create(
            name="John Doe",
            max_weekly_hours=40,
            working_hours=20,
            team=self.team,
        )
        self.group = Group.objects.create(
            name="1º ESO A",
            stage=GroupEducationalStage.SECONDARY,
            team=self.team,
        )

    def test_list_and_retrieve_subject(self):
        subject = Subject.objects.create(
            name="Science",
            weekly_hours=4,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )

        list_response = self.client.get(reverse("subject-list"))
        detail_response = self.client.get(reverse("subject-detail", args=[subject.id]))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["name"], "Science")
        self.assertEqual(detail_response.data["stage"], EducationalStage.SECONDARY)
        self.assertEqual(detail_response.data["stage_color"], "orange")

    def test_update_subject(self):
        subject = Subject.objects.create(
            name="History",
            weekly_hours=3,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )

        payload = {
            "name": "History Updated",
            "weekly_hours": 4,
            "type": SubjectType.NORMAL,
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
        self.assertEqual(subject.type, SubjectType.NORMAL)

    def test_delete_subject(self):
        subject = Subject.objects.create(
            name="Art",
            weekly_hours=2,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )

        response = self.client.delete(reverse("subject-detail", args=[subject.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Subject.objects.filter(id=subject.id).exists())

    def test_ignore_duration_if_provided(self):
        payload = {
            "name": "Invalid Subject",
            "weekly_hours": 3,
            "duration": -1.0,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
            "group": self.group.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["duration"], 1.0)

    def test_reject_invalid_weekly_hours(self):
        payload = {
            "name": "Invalid Subject",
            "weekly_hours": -5,
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
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )

        self.assertEqual(subject.teacher.id, self.teacher.id)
        self.assertEqual(self.teacher.subjects.count(), 1)
        self.assertEqual(self.teacher.subjects.first().name, "Physics")

    def test_reject_missing_group(self):
        payload = {
            "name": "Sin curso",
            "weekly_hours": 3,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("group", response.data)

    def test_reject_whitespace_only_name(self):
        payload = {
            "name": "   ",
            "weekly_hours": 3,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
            "group": self.group.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_reject_case_insensitive_duplicate_name(self):
        Subject.objects.create(
            name="Historia",
            weekly_hours=3,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )

        payload = {
            "name": "historia",
            "weekly_hours": 2,
            "type": SubjectType.NORMAL,
            "teacher": self.teacher.id,
            "group": self.group.id,
        }

        response = self.client.post(reverse("subject-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_allow_same_name_in_different_team(self):
        Subject.objects.create(
            name="Historia Compartida",
            weekly_hours=3,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )
        other_user, other_team = self.create_isolated_user(
            email_prefix="subject-api-other"
        )
        other_teacher = Teacher.objects.create(
            name="Other Teacher",
            max_weekly_hours=40,
            working_hours=20,
            team=other_team,
        )
        other_group = Group.objects.create(
            name="2º ESO B",
            stage=GroupEducationalStage.SECONDARY,
            team=other_team,
        )
        self.client.force_authenticate(other_user)

        response = self.client.post(
            reverse("subject-list"),
            {
                "name": "historia compartida",
                "weekly_hours": 2,
                "type": SubjectType.NORMAL,
                "teacher": other_teacher.id,
                "group": other_group.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Subject.objects.filter(name__iexact="Historia Compartida").count(), 2
        )
        self.assertTrue(
            Subject.objects.filter(
                name__iexact="Historia Compartida",
                team=other_team,
            ).exists()
        )

    def test_list_summary_options_include_type(self):
        Subject.objects.create(
            name="Tutoria",
            weekly_hours=1,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )

        response = self.client.get(reverse("subject-list") + "?summary=options")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Tutoria")
        self.assertEqual(response.data[0]["type"], SubjectType.NORMAL)
        self.assertEqual(set(response.data[0].keys()), {"id", "name", "type"})
