from datetime import timedelta
from unittest import skipIf

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from classroom.models import Classroom
from group.models import EducationalStage, Group
from schedule.algorithm import assignment as schedule_assignment
from schedule.algorithm.slots import (
    build_slot_preference_index,
    build_weekly_slots,
    slot_preference_key_from_datetime,
)
from schedule.models import Schedule
from subject.models import EducationalStage as SubjectEducationalStage
from subject.models import Subject, SubjectTimePreferenceState, SubjectType
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

    def generate_schedule(self):
        return self.client.post(reverse("schedule-generate"), {}, format="json")

    def assert_generate_bad_request_with_detail(self, response, detail_snippet):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertIn(detail_snippet, response.data["detail"])

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

        response = self.generate_schedule()

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

        response = self.generate_schedule()

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

        response = self.generate_schedule()
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

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        group_schedules = list(
            Schedule.objects.filter(group=self.group).order_by("start_time")
        )
        unique_starts = {item.start_time for item in group_schedules}
        self.assertEqual(len(unique_starts), len(group_schedules))

    def test_generate_basic_schedule_requires_teacher(self):
        Teacher.objects.all().delete()

        response = self.generate_schedule()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_generate_basic_schedule_rejects_teacher_over_max_weekly_hours(self):
        self.teacher.max_weekly_hours = 4
        self.teacher.save(update_fields=["max_weekly_hours"])

        response = self.generate_schedule()

        self.assert_generate_bad_request_with_detail(
            response,
            "exceeds max weekly hours",
        )

    def test_generate_rejects_teacher_over_max_with_multiple_subjects(self):
        group_2 = Group.objects.create(name="2B", stage=EducationalStage.PRIMARY)
        Subject.objects.create(
            name="Physics",
            weekly_hours=3,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=group_2,
        )
        self.teacher.max_weekly_hours = 7
        self.teacher.save(update_fields=["max_weekly_hours"])

        # Same teacher teaches 5h (Math) + 3h (Physics) = 8h, which exceeds 7h.
        response = self.generate_schedule()

        self.assert_generate_bad_request_with_detail(
            response,
            "exceeds max weekly hours",
        )

    def test_generate_rejects_group_over_weekly_capacity_for_primary(self):
        self.teacher.max_weekly_hours = 40
        self.teacher.save(update_fields=["max_weekly_hours"])
        Subject.objects.create(
            name="Science",
            weekly_hours=21,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )

        # 5h (Math) + 21h (Science) = 26h, above PRIMARY weekly limit (25h).
        response = self.generate_schedule()

        self.assert_generate_bad_request_with_detail(
            response,
            "exceeds weekly capacity",
        )

    def test_generate_respects_group_daily_capacity_for_primary(self):
        self.teacher.max_weekly_hours = 30
        self.teacher.save(update_fields=["max_weekly_hours"])
        self.subject.weekly_hours = 25
        self.subject.save(update_fields=["weekly_hours"])

        response = self.generate_schedule()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        daily_counts = {}
        group_schedules = Schedule.objects.filter(group=self.group)
        for schedule in group_schedules:
            day_key = schedule.start_time.date()
            daily_counts[day_key] = daily_counts.get(day_key, 0) + 1

        self.assertEqual(group_schedules.count(), 25)
        self.assertEqual(len(daily_counts), 5)
        self.assertTrue(all(count <= 5 for count in daily_counts.values()))

    @skipIf(
        schedule_assignment.cp_model is None,
        "Requires OR-Tools CP-SAT to validate soft constraints.",
    )
    def test_generate_tc_sessions_spread_across_distinct_slots_when_feasible(self):
        self.subject.weekly_hours = 1
        self.subject.save(update_fields=["weekly_hours"])

        teacher_2 = Teacher.objects.create(
            name="Lucia Martin",
            max_weekly_hours=20,
            working_hours=12,
        )
        group_2 = Group.objects.create(name="2A", stage=EducationalStage.PRIMARY)

        Subject.objects.create(
            name="TC 1A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=self.teacher,
            group=self.group,
        )
        Subject.objects.create(
            name="TC 2A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=teacher_2,
            group=group_2,
        )

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tc_schedules = list(
            Schedule.objects.filter(subject__type=SubjectType.TC).order_by("start_time")
        )
        unique_tc_starts = {item.start_time for item in tc_schedules}

        self.assertEqual(len(tc_schedules), 4)
        self.assertEqual(len(unique_tc_starts), 4)

    def test_generate_rejects_subject_with_all_slots_marked_unavailable(self):
        all_slot_keys = build_slot_preference_index(slots=build_weekly_slots()).values()
        self.subject.time_preferences = {
            key: SubjectTimePreferenceState.UNAVAILABLE for key in all_slot_keys
        }
        self.subject.save(update_fields=["time_preferences"])

        response = self.generate_schedule()

        self.assert_generate_bad_request_with_detail(
            response,
            "Could not generate a feasible schedule",
        )

    @skipIf(
        schedule_assignment.cp_model is None,
        "Requires OR-Tools CP-SAT to validate soft constraints.",
    )
    def test_generate_prefers_prefer_yes_over_prefer_no_for_subject(self):
        self.subject.weekly_hours = 1
        slot_pref_index = build_slot_preference_index(slots=build_weekly_slots())
        first_slot_key = slot_pref_index[0]
        second_slot_key = slot_pref_index[1]
        self.subject.time_preferences = {
            first_slot_key: SubjectTimePreferenceState.PREFER_NO,
            second_slot_key: SubjectTimePreferenceState.PREFER_YES,
        }
        self.subject.save(update_fields=["weekly_hours", "time_preferences"])

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        generated = Schedule.objects.get(subject=self.subject)
        generated_slot_key = slot_preference_key_from_datetime(
            slot=generated.start_time
        )
        self.assertEqual(generated_slot_key, second_slot_key)
