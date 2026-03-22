from datetime import timedelta
from unittest import skipIf

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from classroom.models import Classroom
from common.test_utils import AuthenticatedAdminAPIMixin
from group.models import EducationalStage, Group
from schedule.algorithm import assignment as schedule_assignment
from schedule.algorithm.slots import (
    build_slot_preference_index,
    build_weekly_slots,
    slot_preference_key_from_datetime,
)
from schedule.constants import AUTO_GENERATED_OBSERVATION
from schedule.models import Schedule
from subject.models import EducationalStage as SubjectEducationalStage
from subject.models import Subject, SubjectTimePreferenceState, SubjectType
from teacher.models import Teacher, TeacherTimePreferenceState
from user.models import RoleChoices


class ScheduleApiTests(AuthenticatedAdminAPIMixin, APITestCase):
    def setUp(self):
        self.authenticate_admin(email_prefix="schedule-api")
        self.other_user = self.create_user(
            email="schedule-api-2@test.com",
            role=RoleChoices.DIRECTOR,
            given_name="Api2",
            family_name="Tester2",
        )

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

    def create_schedule(
        self,
        *,
        name="Science",
        start_time=None,
        end_time=None,
        observations="Lab class",
        created_by="",
        updated_by="",
        teacher=None,
        classroom=None,
        group=None,
        subject=None,
        users=None,
    ):
        start_time = start_time or (timezone.now() + timedelta(days=1))
        end_time = end_time or (start_time + timedelta(hours=1))
        schedule = Schedule.objects.create(
            name=name,
            start_time=start_time,
            end_time=end_time,
            observations=observations,
            teacher=teacher or self.teacher,
            classroom=classroom or self.classroom,
            group=group or self.group,
            subject=subject or self.subject,
            created_by=created_by,
            updated_by=updated_by,
        )
        for user in users or [self.user]:
            schedule.users.add(user)
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

    def test_save_generated_schedules_in_bulk(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        schedule_1 = self.create_schedule(
            name="Auto Session 1",
            start_time=start_time,
            end_time=end_time,
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        schedule_2 = self.create_schedule(
            name="Auto Session 2",
            start_time=start_time + timedelta(hours=1),
            end_time=end_time + timedelta(hours=1),
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        response = self.client.post(
            reverse("schedule-save-generated"),
            {
                "timetable_name": "Horario Guardado",
                "schedule_ids": [schedule_1.id, schedule_2.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["saved_count"], 2)

        schedule_1.refresh_from_db()
        schedule_2.refresh_from_db()
        self.assertEqual(schedule_1.name, "Horario Guardado")
        self.assertEqual(schedule_2.name, "Horario Guardado")
        self.assertEqual(schedule_1.observations, "Saved timetable: Horario Guardado")
        self.assertEqual(schedule_2.observations, "Saved timetable: Horario Guardado")

    def test_save_generated_schedules_in_bulk_assigns_additional_users(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        schedule = self.create_schedule(
            name="Auto Session 1",
            start_time=start_time,
            end_time=end_time,
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        response = self.client.post(
            reverse("schedule-save-generated"),
            {
                "timetable_name": "Horario Compartido",
                "schedule_ids": [schedule.id],
                "user_ids": [self.other_user.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        schedule.refresh_from_db()
        self.assertTrue(schedule.users.filter(id=self.user.id).exists())
        self.assertTrue(schedule.users.filter(id=self.other_user.id).exists())

    def test_save_generated_rejects_non_auto_generated_sessions(self):
        schedule = self.create_schedule()
        schedule.created_by = self.user.email
        schedule.updated_by = self.user.email
        schedule.save(update_fields=["created_by", "updated_by"])

        response = self.client.post(
            reverse("schedule-save-generated"),
            {
                "timetable_name": "Horario Invalido",
                "schedule_ids": [schedule.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_saved_endpoint_returns_only_saved_schedules_for_current_user(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        saved_schedule = self.create_schedule(
            name="Horario Guardado",
            start_time=start_time,
            end_time=end_time,
            observations="Saved timetable: Horario Guardado",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        self.create_schedule(
            name="Auto Session",
            start_time=start_time + timedelta(hours=1),
            end_time=end_time + timedelta(hours=1),
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        self.create_schedule(
            name="Horario Otro Usuario",
            start_time=start_time + timedelta(hours=2),
            end_time=end_time + timedelta(hours=2),
            observations="Saved timetable: Horario Otro Usuario",
            created_by=self.other_user.email,
            updated_by=self.other_user.email,
            users=[self.other_user],
        )

        response = self.client.get(reverse("schedule-saved"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], saved_schedule.id)

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

    def test_generate_assigns_only_compatible_classrooms(self):
        self.classroom.classroom_type = "STANDARD"
        self.classroom.save(update_fields=["classroom_type"])
        lab = Classroom.objects.create(name="Laboratorio 1", classroom_type="LAB")

        self.subject.required_classroom_type = "lab"
        self.subject.save(update_fields=["required_classroom_type"])

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        generated_classroom_ids = set(
            Schedule.objects.filter(subject=self.subject).values_list(
                "classroom_id", flat=True
            )
        )
        self.assertEqual(generated_classroom_ids, {lab.id})

    def test_generate_rejects_subject_without_compatible_classroom(self):
        self.classroom.classroom_type = "STANDARD"
        self.classroom.save(update_fields=["classroom_type"])
        self.subject.required_classroom_type = "LAB"
        self.subject.save(update_fields=["required_classroom_type"])

        response = self.generate_schedule()

        self.assert_generate_bad_request_with_detail(
            response,
            "compatible classroom",
        )

    def test_generate_spreads_sessions_when_one_compatible_classroom_is_shared(self):
        self.classroom.classroom_type = "LAB"
        self.classroom.save(update_fields=["classroom_type"])
        self.subject.weekly_hours = 1
        self.subject.required_classroom_type = "LAB"
        self.subject.save(update_fields=["weekly_hours", "required_classroom_type"])

        teacher_2 = Teacher.objects.create(
            name="Elena Ruiz",
            max_weekly_hours=20,
            working_hours=8,
        )
        group_2 = Group.objects.create(name="2A", stage=EducationalStage.PRIMARY)
        other_subject = Subject.objects.create(
            name="Science Lab",
            weekly_hours=1,
            duration=1.0,
            preferred_time_slot="Morning",
            required_classroom_type="lab",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=teacher_2,
            group=group_2,
        )

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        generated = list(
            Schedule.objects.filter(subject__in=[self.subject, other_subject]).order_by(
                "start_time"
            )
        )
        self.assertEqual(len(generated), 2)
        self.assertEqual({item.classroom_id for item in generated}, {self.classroom.id})
        self.assertEqual(
            len({item.start_time for item in generated}),
            2,
            "Two sessions that share a single compatible classroom must not overlap.",
        )

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

    def test_generate_rejects_teacher_with_all_slots_marked_unavailable(self):
        all_slot_keys = build_slot_preference_index(slots=build_weekly_slots()).values()
        self.teacher.time_preferences = {
            key: TeacherTimePreferenceState.UNAVAILABLE for key in all_slot_keys
        }
        self.teacher.save(update_fields=["time_preferences"])

        response = self.generate_schedule()

        self.assert_generate_bad_request_with_detail(
            response,
            "Could not generate a feasible schedule",
        )

    @skipIf(
        schedule_assignment.cp_model is None,
        "Requires OR-Tools CP-SAT to validate soft constraints.",
    )
    def test_generate_prefers_teacher_prefer_yes_over_prefer_no(self):
        self.subject.weekly_hours = 1
        slot_pref_index = build_slot_preference_index(slots=build_weekly_slots())
        first_slot_key = slot_pref_index[0]
        second_slot_key = slot_pref_index[1]
        self.teacher.time_preferences = {
            first_slot_key: TeacherTimePreferenceState.PREFER_NO,
            second_slot_key: TeacherTimePreferenceState.PREFER_YES,
        }
        self.subject.save(update_fields=["weekly_hours"])
        self.teacher.save(update_fields=["time_preferences"])

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        generated = Schedule.objects.get(subject=self.subject)
        generated_slot_key = slot_preference_key_from_datetime(
            slot=generated.start_time
        )
        self.assertEqual(generated_slot_key, second_slot_key)

    def test_generate_spreads_subject_sessions_across_days(self):
        response = self.generate_schedule()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        subject_schedules = Schedule.objects.filter(subject=self.subject)
        distinct_days = {s.start_time.date() for s in subject_schedules}
        self.assertGreaterEqual(
            len(distinct_days),
            4,
            "Expected subject sessions to be spread across at least 4 different days.",
        )

    @skipIf(
        schedule_assignment.cp_model is None,
        "Requires OR-Tools CP-SAT to validate soft constraints.",
    )
    def test_generate_minimizes_teacher_intraday_gaps(self):
        """F-29: solver should prefer compact schedules over fragmented ones."""
        # Allow only 3 Monday slots: position 0 (08:30) and positions 4-5 (13:00, 14:00).
        # With weekly_hours=2 the solver must pick exactly 2 of those 3 slots.
        # Compact choice (pos 4 + pos 5) yields 0 internal gaps, while any pair
        # that includes pos 0 creates 3-4 internal gaps → F-29 should avoid it.
        slot_pref_index = build_slot_preference_index(slots=build_weekly_slots())
        allowed = {"MON_08:30", "MON_13:00", "MON_14:00"}
        self.teacher.time_preferences = {
            key: TeacherTimePreferenceState.UNAVAILABLE
            for key in slot_pref_index.values()
            if key not in allowed
        }
        self.subject.weekly_hours = 2
        self.subject.save(update_fields=["weekly_hours"])
        self.teacher.save(update_fields=["time_preferences"])

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        schedules = Schedule.objects.filter(subject=self.subject)
        assigned_keys = {
            slot_preference_key_from_datetime(slot=s.start_time) for s in schedules
        }
        self.assertEqual(len(assigned_keys), 2)
        # The compact pair should win; MON_08:30 (far from 13:00/14:00) must not appear.
        self.assertNotIn(
            "MON_08:30",
            assigned_keys,
            "Expected compact assignment (MON_13:00 + MON_14:00) but got a fragmented one.",
        )

    def test_generate_rejects_group_intraday_gaps(self):
        """F-30: a group's timetable cannot contain intra-day gaps."""
        self.subject.weekly_hours = 1
        self.subject.save(update_fields=["weekly_hours"])

        teacher_2 = Teacher.objects.create(
            name="Lucia Lopez",
            max_weekly_hours=20,
            working_hours=8,
        )
        Subject.objects.create(
            name="Science",
            weekly_hours=1,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=teacher_2,
            group=self.group,
        )

        slot_pref_index = build_slot_preference_index(slots=build_weekly_slots())
        allowed = {"MON_08:30", "MON_13:00"}

        self.teacher.time_preferences = {
            key: TeacherTimePreferenceState.UNAVAILABLE
            for key in slot_pref_index.values()
            if key not in allowed
        }
        teacher_2.time_preferences = {
            key: TeacherTimePreferenceState.UNAVAILABLE
            for key in slot_pref_index.values()
            if key not in allowed
        }
        self.teacher.save(update_fields=["time_preferences"])
        teacher_2.save(update_fields=["time_preferences"])

        response = self.generate_schedule()

        self.assert_generate_bad_request_with_detail(
            response,
            "Could not generate a feasible schedule",
        )
