from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from classroom.models import Classroom
from group.models import EducationalStage, Group
from schedule.models import Schedule
from subject.models import EducationalStage as SubjectEducationalStage
from subject.models import Subject, SubjectType
from teacher.models import Teacher
from user.models import RoleChoices, User


class ScheduleApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="schedule-api@test.com",
            password="StrongPassword123!",
            given_name="Api",
            family_name="Tester",
            role=RoleChoices.ADMINISTRATOR,
        )
        self.other_user = User.objects.create_user(
            email="schedule-api-2@test.com",
            password="StrongPassword123!",
            given_name="Api2",
            family_name="Tester2",
            role=RoleChoices.DIRECTOR,
        )
        self.client.force_authenticate(self.user)

        self.teacher = Teacher.objects.create(
            name="Ana Perez",
            max_weekly_hours=20,
            working_hours=12,
        )
        self.classroom = Classroom.objects.create(name="Aula 1A")
        self.group = Group.objects.create(name="1A", stage=EducationalStage.PRIMARY)
        self.subject = Subject.objects.create(
            name="Mathematics",
            weekly_hours=5,
            duration=1.5,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )

    def build_payload(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        return {
            "name": "Math Monday",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "observations": "Bring calculators",
            "teacher": self.teacher.id,
            "classroom": self.classroom.id,
            "group": self.group.id,
            "subject": self.subject.id,
            "users": [self.user.id],
        }

    def create_schedule(self):
        schedule = Schedule.objects.create(
            name="Science",
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=2),
            observations="Lab class",
            teacher=self.teacher,
            classroom=self.classroom,
            group=self.group,
            subject=self.subject,
        )
        schedule.users.add(self.user)
        return schedule

    def test_create_schedule(self):
        response = self.client.post(
            reverse("schedule-list"),
            self.build_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 1)

    def test_list_and_retrieve_schedule(self):
        schedule = self.create_schedule()

        list_response = self.client.get(reverse("schedule-list"))
        detail_response = self.client.get(
            reverse("schedule-detail", args=[schedule.id])
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["name"], "Science")

    def test_update_schedule(self):
        schedule = self.create_schedule()
        new_end = timezone.now() + timedelta(days=2, hours=2)

        payload = {
            "observations": "Updated class note",
            "end_time": new_end.isoformat(),
            "users": [self.user.id, self.other_user.id],
        }

        response = self.client.patch(
            reverse("schedule-detail", args=[schedule.id]),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        schedule.refresh_from_db()
        self.assertEqual(schedule.observations, "Updated class note")
        self.assertEqual(schedule.users.count(), 2)

    def test_delete_schedule(self):
        schedule = self.create_schedule()

        response = self.client.delete(reverse("schedule-detail", args=[schedule.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Schedule.objects.filter(id=schedule.id).exists())

    def test_reject_if_end_time_is_not_greater_than_start_time(self):
        start_time = timezone.now() + timedelta(days=1)
        payload = self.build_payload()
        payload["start_time"] = start_time.isoformat()
        payload["end_time"] = start_time.isoformat()

        response = self.client.post(reverse("schedule-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_time", response.data)

    def test_reject_empty_users(self):
        payload = self.build_payload()
        payload["users"] = []

        response = self.client.post(reverse("schedule-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("users", response.data)

    def test_reject_missing_subject(self):
        payload = self.build_payload()
        payload.pop("subject")

        response = self.client.post(reverse("schedule-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("subject", response.data)

    def test_generate_basic_schedule(self):
        Classroom.objects.all().delete()

        response = self.client.post(reverse("schedule-generate"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("schedules", response.data)
        self.assertEqual(response.data["generated_count"], self.subject.weekly_hours)
        self.assertEqual(Schedule.objects.count(), self.subject.weekly_hours)

        schedule = Schedule.objects.first()
        self.assertEqual(schedule.teacher_id, self.teacher.id)
        self.assertEqual(schedule.group_id, self.group.id)
        self.assertEqual(schedule.users.count(), 1)
        self.assertEqual(schedule.users.first().id, self.user.id)
        self.assertIsNotNone(schedule.classroom_id)
        self.assertIsNotNone(schedule.group_id)

    def test_generate_basic_schedule_avoids_teacher_overlap(self):
        Subject.objects.create(
            name="Physics",
            weekly_hours=1,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )

        response = self.client.post(reverse("schedule-generate"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        teacher_schedules = list(
            Schedule.objects.filter(teacher=self.teacher).order_by("start_time")
        )
        unique_starts = {item.start_time for item in teacher_schedules}
        self.assertEqual(len(unique_starts), len(teacher_schedules))

    def test_generate_basic_schedule_avoids_teacher_overlap_across_groups(self):
        group_2 = Group.objects.create(name="2A", stage=EducationalStage.PRIMARY)
        Subject.objects.create(
            name="Mathematics 2A",
            weekly_hours=5,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=group_2,
        )

        response = self.client.post(reverse("schedule-generate"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        teacher_schedules = list(
            Schedule.objects.filter(teacher=self.teacher).order_by("start_time")
        )
        unique_starts = {item.start_time for item in teacher_schedules}
        self.assertEqual(len(unique_starts), len(teacher_schedules))

    def test_generate_basic_schedule_avoids_group_overlap(self):
        teacher_2 = Teacher.objects.create(
            name="Carlos Torres",
            max_weekly_hours=20,
            working_hours=8,
        )
        Subject.objects.create(
            name="Science",
            weekly_hours=5,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=teacher_2,
            group=self.group,
        )

        response = self.client.post(reverse("schedule-generate"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        group_schedules = list(
            Schedule.objects.filter(group=self.group).order_by("start_time")
        )
        unique_starts = {item.start_time for item in group_schedules}
        self.assertEqual(len(unique_starts), len(group_schedules))

    def test_generate_basic_schedule_requires_teacher(self):
        Teacher.objects.all().delete()

        response = self.client.post(reverse("schedule-generate"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
