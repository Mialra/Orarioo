from datetime import timedelta
from io import BytesIO
from unittest import skipIf

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from auditableEntity.models import AuditActionType, AuditEntry
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
from schedule.views import REPORTLAB_AVAILABLE
from subject.models import EducationalStage as SubjectEducationalStage
from subject.models import Subject, SubjectTimePreferenceState, SubjectType
from teacher.models import Teacher, TeacherTimePreferenceState

try:
    from openpyxl import load_workbook

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class ScheduleApiTests(AuthenticatedAdminAPIMixin, APITestCase):
    def setUp(self):
        self.authenticate_admin(email_prefix="schedule-api")
        self.other_user = self.create_user(
            email="schedule-api-2@test.com",
            given_name="Api2",
            family_name="Tester2",
        )
        self.team.members.add(self.other_user)

        self.teacher = Teacher.objects.create(
            team=self.team,
            name="Ana Perez",
            max_weekly_hours=20,
            working_hours=12,
        )
        self.classroom = Classroom.objects.create(name="Aula 1A", team=self.team)
        self.group = Group.objects.create(
            name="1A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        self.subject = Subject.objects.create(
            team=self.team,
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

    def generate_schedule(self, payload=None):
        return self.client.post(
            reverse("schedule-generate"), payload or {}, format="json"
        )

    def assert_generate_bad_request_with_detail(self, response, detail_snippet):
        del detail_snippet
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertEqual(
            response.data["detail"],
            "Unable to generate schedule with the current input constraints.",
        )
        self.assertEqual(response.data.get("error_code"), "schedule_generation_failed")

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
            team=self.team,
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

    @staticmethod
    def slot_descriptor_from_datetimes(start_time, end_time):
        weekday_to_name = {
            0: "Lunes",
            1: "Martes",
            2: "Miércoles",
            3: "Jueves",
            4: "Viernes",
        }
        local_start = timezone.localtime(start_time)
        local_end = timezone.localtime(end_time)
        return {
            "day": weekday_to_name[local_start.weekday()],
            "start": local_start.strftime("%H:%M"),
            "end": local_end.strftime("%H:%M"),
        }

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

    def test_export_csv_includes_global_schedules(self):
        created_schedule = self.create_schedule(
            name="Horario Usuario 1",
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        self.create_schedule(
            name="Horario Usuario 2",
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.other_user.email,
            updated_by=self.other_user.email,
            users=[self.other_user],
        )

        response = self.client.get(
            reverse("schedule-export"),
            {"export_format": "csv", "source": "generated", "scope": "all"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        csv_text = response.content.decode("utf-8-sig")
        self.assertIn("Día,Inicio,Fin,Asignatura,Profesor,Curso,Aula", csv_text)
        self.assertIn("Mathematics", csv_text)
        self.assertIn("Ana Perez", csv_text)
        self.assertIn("1A", csv_text)
        self.assertIn("Aula 1A", csv_text)
        self.assertIn(
            timezone.localtime(created_schedule.start_time).strftime("%H:%M"),
            csv_text,
        )
        self.assertIn(
            timezone.localtime(created_schedule.end_time).strftime("%H:%M"),
            csv_text,
        )
        self.assertTrue(
            any(
                day_name in csv_text
                for day_name in [
                    "Lunes",
                    "Martes",
                    "Miércoles",
                    "Jueves",
                    "Viernes",
                    "Sábado",
                    "Domingo",
                ]
            )
        )
        self.assertIn("orarioo_generated_schedule_", response["Content-Disposition"])

    def test_export_csv_by_group_entity_filter(self):
        other_group = Group.objects.create(
            name="2A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        other_subject = Subject.objects.create(
            team=self.team,
            name="Language 2A",
            weekly_hours=3,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=other_group,
        )

        self.create_schedule(
            name="Sesion 1A",
            group=self.group,
            subject=self.subject,
            observations=AUTO_GENERATED_OBSERVATION,
        )
        self.create_schedule(
            name="Sesion 2A",
            group=other_group,
            subject=other_subject,
            observations=AUTO_GENERATED_OBSERVATION,
        )

        response = self.client.get(
            reverse("schedule-export"),
            {
                "export_format": "csv",
                "source": "generated",
                "scope": "entity",
                "entity_type": "group",
                "entity_id": self.group.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csv_text = response.content.decode("utf-8-sig")
        self.assertIn("Mathematics", csv_text)
        self.assertNotIn("Language 2A", csv_text)

    @skipIf(not REPORTLAB_AVAILABLE, "reportlab is not installed")
    def test_export_pdf_saved_returns_pdf_file(self):
        self.create_schedule(
            name="Horario Guardado",
            observations="Saved timetable",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        response = self.client.get(
            reverse("schedule-export"),
            {
                "export_format": "pdf",
                "source": "saved",
                "scope": "all",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn(
            'filename="Horario Guardado.pdf"',
            response["Content-Disposition"],
        )

    def test_export_entity_scope_requires_valid_entity_data(self):
        response = self.client.get(
            reverse("schedule-export"),
            {
                "export_format": "csv",
                "source": "all",
                "scope": "entity",
                "entity_type": "group",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    @skipIf(not OPENPYXL_AVAILABLE, "openpyxl is not installed")
    def test_export_cards_mode_with_specific_teacher_without_teacher_all(self):
        second_teacher = Teacher.objects.create(
            team=self.team,
            name="Julian",
            max_weekly_hours=20,
            working_hours=12,
        )
        second_subject = Subject.objects.create(
            team=self.team,
            name="Science",
            weekly_hours=3,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=second_teacher,
            group=self.group,
        )

        self.create_schedule(
            name="Sesion Ana",
            teacher=self.teacher,
            subject=self.subject,
            observations=AUTO_GENERATED_OBSERVATION,
        )
        self.create_schedule(
            name="Sesion Julian",
            teacher=second_teacher,
            subject=second_subject,
            observations=AUTO_GENERATED_OBSERVATION,
        )

        response = self.client.get(
            reverse("schedule-export"),
            {
                "export_format": "csv",
                "source": "generated",
                "selection_mode": "cards",
                "group_all": "0",
                "teacher_all": "0",
                "classroom_all": "0",
                "subject_all": "0",
                "teacher_ids": str(second_teacher.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(filename=BytesIO(response.content))
        self.assertGreaterEqual(len(workbook.sheetnames), 1)
        first_sheet = workbook[workbook.sheetnames[0]]
        values = [
            str(value)
            for row in first_sheet.iter_rows(values_only=True)
            for value in row
            if value is not None
        ]
        joined = " ".join(values)
        self.assertIn("Julian", joined)
        self.assertNotIn("Ana Perez", joined)

    @skipIf(not OPENPYXL_AVAILABLE, "openpyxl is not installed")
    def test_export_cards_mode_with_no_selection_returns_only_header(self):
        self.create_schedule(
            name="Sesion Base",
            observations=AUTO_GENERATED_OBSERVATION,
        )

        response = self.client.get(
            reverse("schedule-export"),
            {
                "export_format": "csv",
                "source": "generated",
                "selection_mode": "cards",
                "group_all": "0",
                "teacher_all": "0",
                "classroom_all": "0",
                "subject_all": "0",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workbook = load_workbook(filename=BytesIO(response.content))
        self.assertEqual(workbook.sheetnames, ["Sin datos"])
        sheet = workbook["Sin datos"]
        self.assertEqual(sheet.max_row, 1)

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

    def test_reject_whitespace_only_name(self):
        payload = self.build_payload()
        payload["name"] = "    "

        response = self.client.post(reverse("schedule-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

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
        AuditEntry.objects.all().delete()

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
        entries = list(
            AuditEntry.objects.filter(
                entity_type="schedule",
                action_type=AuditActionType.CREATE,
            )
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].entity_name, "Generacion automatica")
        self.assertEqual(
            entries[0].changed_fields,
            [{"campo": "Sesiones generadas", "valor_nuevo": self.subject.weekly_hours}],
        )

    def test_generate_basic_schedule_avoids_teacher_overlap(self):
        Subject.objects.create(
            team=self.team,
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
        group_2 = Group.objects.create(
            name="2A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        Classroom.objects.create(name="Aula 2A", team=self.team)
        Subject.objects.create(
            team=self.team,
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
            team=self.team,
            name="Carlos Torres",
            max_weekly_hours=20,
            working_hours=8,
        )
        Subject.objects.create(
            team=self.team,
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
        AuditEntry.objects.all().delete()

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
        self.assertGreaterEqual(
            AuditEntry.objects.filter(
                entity_type="schedule",
                action_type=AuditActionType.UPDATE,
            ).count(),
            2,
        )

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

    def test_apply_manual_change_replans_saved_timetable(self):
        slots = build_weekly_slots()
        primary_slots = [slot for slot in slots if slot.get("stage") == "PRIMARY"]
        self.assertGreaterEqual(len(primary_slots), 3)

        saved_observation = "Saved timetable: Horario Manual Test"
        schedule_to_move = self.create_schedule(
            name="Horario Manual Test",
            start_time=primary_slots[0]["start"],
            end_time=primary_slots[0]["end"],
            observations=saved_observation,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        self.create_schedule(
            name="Horario Manual Test",
            start_time=primary_slots[1]["start"],
            end_time=primary_slots[1]["end"],
            observations=saved_observation,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        AuditEntry.objects.all().delete()

        target_slot_index = slots.index(primary_slots[2])

        response = self.client.post(
            reverse("schedule-apply-manual-change"),
            {
                "schedule_id": schedule_to_move.id,
                "new_slot_index": target_slot_index,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("schedules", response.data)

        schedule_to_move.refresh_from_db()
        self.assertEqual(schedule_to_move.start_time, primary_slots[2]["start"])
        self.assertEqual(schedule_to_move.end_time, primary_slots[2]["end"])
        self.assertGreaterEqual(
            AuditEntry.objects.filter(
                entity_type="schedule",
                action_type=AuditActionType.UPDATE,
            ).count(),
            1,
        )

    def test_move_endpoint_moves_single_generated_session(self):
        slots = build_weekly_slots()
        primary_slots = [slot for slot in slots if slot.get("stage") == "PRIMARY"]
        self.assertGreaterEqual(len(primary_slots), 3)

        source_schedule = self.create_schedule(
            name="Auto Move",
            start_time=primary_slots[0]["start"],
            end_time=primary_slots[0]["end"],
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        source_slot = self.slot_descriptor_from_datetimes(
            source_schedule.start_time,
            source_schedule.end_time,
        )
        target_slot = self.slot_descriptor_from_datetimes(
            primary_slots[2]["start"],
            primary_slots[2]["end"],
        )

        response = self.client.post(
            reverse("schedule-move"),
            {
                "mode": "move",
                "source_slot": {
                    "schedule_id": source_schedule.id,
                    **source_slot,
                },
                "target_slot": target_slot,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mode"], "move")
        self.assertFalse(response.data["no_changes"])

        source_schedule.refresh_from_db()
        self.assertEqual(source_schedule.start_time, primary_slots[2]["start"])
        self.assertEqual(source_schedule.end_time, primary_slots[2]["end"])

    def test_move_endpoint_swaps_sessions_when_target_provided(self):
        slots = build_weekly_slots()
        primary_slots = [slot for slot in slots if slot.get("stage") == "PRIMARY"]
        self.assertGreaterEqual(len(primary_slots), 2)

        other_teacher = Teacher.objects.create(
            team=self.team,
            name="Lucia Martin",
            max_weekly_hours=20,
            working_hours=12,
        )
        other_classroom = Classroom.objects.create(name="Aula 2A", team=self.team)
        other_group = Group.objects.create(
            name="2A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        other_subject = Subject.objects.create(
            team=self.team,
            name="Lengua 2A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=other_teacher,
            group=other_group,
        )

        source_schedule = self.create_schedule(
            name="Auto Source",
            start_time=primary_slots[0]["start"],
            end_time=primary_slots[0]["end"],
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        target_schedule = self.create_schedule(
            name="Auto Target",
            start_time=primary_slots[1]["start"],
            end_time=primary_slots[1]["end"],
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            teacher=other_teacher,
            classroom=other_classroom,
            group=other_group,
            subject=other_subject,
            users=[self.user],
        )

        source_slot = self.slot_descriptor_from_datetimes(
            source_schedule.start_time,
            source_schedule.end_time,
        )
        target_slot = self.slot_descriptor_from_datetimes(
            target_schedule.start_time,
            target_schedule.end_time,
        )

        response = self.client.post(
            reverse("schedule-move"),
            {
                "mode": "swap",
                "source_slot": {
                    "schedule_id": source_schedule.id,
                    **source_slot,
                },
                "target_slot": {
                    "schedule_id": target_schedule.id,
                    **target_slot,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mode"], "swap")

        source_schedule.refresh_from_db()
        target_schedule.refresh_from_db()
        self.assertEqual(source_schedule.start_time, primary_slots[1]["start"])
        self.assertEqual(source_schedule.end_time, primary_slots[1]["end"])
        self.assertEqual(target_schedule.start_time, primary_slots[0]["start"])
        self.assertEqual(target_schedule.end_time, primary_slots[0]["end"])

    def test_move_endpoint_rejects_teacher_overlap_conflict(self):
        slots = build_weekly_slots()
        primary_slots = [slot for slot in slots if slot.get("stage") == "PRIMARY"]
        self.assertGreaterEqual(len(primary_slots), 3)

        other_group = Group.objects.create(
            name="3A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        other_subject = Subject.objects.create(
            team=self.team,
            name="Ciencias 3A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=other_group,
        )

        source_schedule = self.create_schedule(
            name="Auto Source Conflict",
            start_time=primary_slots[0]["start"],
            end_time=primary_slots[0]["end"],
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        blocker_schedule = self.create_schedule(
            name="Auto Blocker",
            start_time=primary_slots[2]["start"],
            end_time=primary_slots[2]["end"],
            observations=AUTO_GENERATED_OBSERVATION,
            created_by=self.user.email,
            updated_by=self.user.email,
            group=other_group,
            subject=other_subject,
            users=[self.user],
        )

        source_slot = self.slot_descriptor_from_datetimes(
            source_schedule.start_time,
            source_schedule.end_time,
        )
        target_slot = self.slot_descriptor_from_datetimes(
            blocker_schedule.start_time,
            blocker_schedule.end_time,
        )

        response = self.client.post(
            reverse("schedule-move"),
            {
                "mode": "move",
                "source_slot": {
                    "schedule_id": source_schedule.id,
                    **source_slot,
                },
                "target_slot": target_slot,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertIn("Teacher conflict", response.data["detail"])

        source_schedule.refresh_from_db()
        self.assertEqual(source_schedule.start_time, primary_slots[0]["start"])
        self.assertEqual(source_schedule.end_time, primary_slots[0]["end"])

    def test_move_endpoint_allows_saved_move_with_conflicts_in_other_timetables(self):
        slots = build_weekly_slots()
        primary_slots = [slot for slot in slots if slot.get("stage") == "PRIMARY"]
        self.assertGreaterEqual(len(primary_slots), 3)

        saved_name = "Horario Guardado Scope"
        saved_observation = f"Saved timetable: {saved_name}"
        source_schedule = self.create_schedule(
            name=saved_name,
            start_time=primary_slots[0]["start"],
            end_time=primary_slots[0]["end"],
            observations=saved_observation,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        # Same resources in another saved timetable should not block this move.
        other_saved_observation = "Saved timetable: Horario Distinto"
        blocker_other_timetable = self.create_schedule(
            name="Horario Distinto",
            start_time=primary_slots[2]["start"],
            end_time=primary_slots[2]["end"],
            observations=other_saved_observation,
            created_by=self.user.email,
            updated_by=self.user.email,
            teacher=self.teacher,
            classroom=self.classroom,
            group=self.group,
            subject=self.subject,
            users=[self.user],
        )

        source_slot = self.slot_descriptor_from_datetimes(
            source_schedule.start_time,
            source_schedule.end_time,
        )
        target_slot = self.slot_descriptor_from_datetimes(
            blocker_other_timetable.start_time,
            blocker_other_timetable.end_time,
        )

        response = self.client.post(
            reverse("schedule-move"),
            {
                "mode": "move",
                "source_slot": {
                    "schedule_id": source_schedule.id,
                    **source_slot,
                },
                "target_slot": target_slot,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mode"], "move")

        source_schedule.refresh_from_db()
        blocker_other_timetable.refresh_from_db()
        self.assertEqual(source_schedule.start_time, primary_slots[2]["start"])
        self.assertEqual(source_schedule.end_time, primary_slots[2]["end"])
        self.assertEqual(blocker_other_timetable.start_time, primary_slots[2]["start"])
        self.assertEqual(blocker_other_timetable.end_time, primary_slots[2]["end"])

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

    def test_save_generated_rejects_whitespace_only_timetable_name(self):
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
                "timetable_name": "   ",
                "schedule_ids": [schedule.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("timetable_name", response.data)

    def test_save_generated_rejects_duplicate_schedule_ids(self):
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
                "timetable_name": "Horario Duplicado",
                "schedule_ids": [schedule.id, schedule.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("schedule_ids", response.data)

    def test_save_generated_rejects_existing_timetable_name(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        self.create_schedule(
            name="Horario Repetido",
            start_time=start_time,
            end_time=end_time,
            observations="Saved timetable: Horario Repetido",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        auto_schedule = self.create_schedule(
            name="Auto Session 1",
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
                "timetable_name": "Horario Repetido",
                "schedule_ids": [auto_schedule.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("timetable_name", response.data)
        auto_schedule.refresh_from_db()
        self.assertEqual(auto_schedule.observations, AUTO_GENERATED_OBSERVATION)

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

    def test_saved_summary_endpoint_returns_lightweight_items(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        self.create_schedule(
            name="Horario Ligero",
            start_time=start_time,
            end_time=end_time,
            observations="Saved timetable: Horario Ligero",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        self.create_schedule(
            name="Horario Ligero",
            start_time=start_time + timedelta(hours=1),
            end_time=end_time + timedelta(hours=1),
            observations="Saved timetable: Horario Ligero",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        response = self.client.get(reverse("schedule-saved-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        first_item = response.data["results"][0]
        self.assertEqual(first_item["name"], "Horario Ligero")
        self.assertEqual(set(first_item.keys()), {"name", "updated_at"})

    def test_saved_detail_endpoint_requires_timetable_name(self):
        response = self.client.get(reverse("schedule-saved-detail"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_saved_detail_endpoint_returns_selected_timetable(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        self.create_schedule(
            name="Horario A",
            start_time=start_time,
            end_time=end_time,
            observations="Saved timetable: Horario A",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        self.create_schedule(
            name="Horario A",
            start_time=start_time + timedelta(hours=1),
            end_time=end_time + timedelta(hours=1),
            observations="Saved timetable: Horario A",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        self.create_schedule(
            name="Horario B",
            start_time=start_time + timedelta(hours=2),
            end_time=end_time + timedelta(hours=2),
            observations="Saved timetable: Horario B",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        response = self.client.get(
            reverse("schedule-saved-detail"),
            {"timetable_name": "Horario A"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertTrue(
            all(item["name"] == "Horario A" for item in response.data["results"])
        )

    def test_delete_saved_timetable_creates_single_audit_entry(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        self.create_schedule(
            name="Horario demo admin",
            start_time=start_time,
            end_time=end_time,
            observations="Saved timetable: Horario demo admin",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        self.create_schedule(
            name="Horario demo admin",
            start_time=start_time + timedelta(hours=1),
            end_time=end_time + timedelta(hours=1),
            observations="Saved timetable: Horario demo admin",
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )
        AuditEntry.objects.all().delete()

        response = self.client.post(
            reverse("schedule-delete-saved-timetable"),
            {"timetable_name": "Horario demo admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            Schedule.objects.filter(
                observations="Saved timetable: Horario demo admin"
            ).exists()
        )
        entries = list(
            AuditEntry.objects.filter(
                entity_type="schedule",
                action_type=AuditActionType.DELETE,
            )
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].entity_name, "Horario demo admin")
        self.assertEqual(
            entries[0].changed_fields,
            [{"campo": "Sesiones eliminadas", "valor_anterior": 2}],
        )

    def test_delete_single_schedule_keeps_minimal_delete_audit(self):
        schedule = self.create_schedule(name="Horario suelto")
        AuditEntry.objects.all().delete()

        response = self.client.delete(reverse("schedule-detail", args=[schedule.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        entry = AuditEntry.objects.get(
            entity_type="schedule",
            action_type=AuditActionType.DELETE,
        )
        self.assertEqual(
            entry.changed_fields,
            [{"campo": "Nombre", "valor_anterior": "Horario suelto"}],
        )

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

    def test_apply_manual_change_rejects_negative_slot_index(self):
        saved_observation = "Saved timetable: Horario Manual Test"
        schedule_to_move = self.create_schedule(
            name="Horario Manual Test",
            observations=saved_observation,
            created_by=self.user.email,
            updated_by=self.user.email,
            users=[self.user],
        )

        response = self.client.post(
            reverse("schedule-apply-manual-change"),
            {
                "schedule_id": schedule_to_move.id,
                "new_slot_index": -1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_slot_index", response.data)

    def test_generate_rejects_teacher_over_max_with_multiple_subjects(self):
        group_2 = Group.objects.create(
            name="2B",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        Subject.objects.create(
            team=self.team,
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
            team=self.team,
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

    def test_generate_rejects_when_recess_supervision_overloads_teacher(self):
        self.teacher.max_weekly_hours = 5
        self.teacher.save(update_fields=["max_weekly_hours"])

        response = self.generate_schedule(
            {
                "recess_supervisors_primary": 1,
            }
        )

        self.assert_generate_bad_request_with_detail(
            response,
            "exceeds max weekly hours",
        )

    def test_generate_excludes_tc_subjects_when_include_tc_is_false(self):
        Subject.objects.create(
            team=self.team,
            name="TC 1A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=self.teacher,
            group=self.group,
        )

        response = self.generate_schedule({"include_tc": False})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            Schedule.objects.filter(
                subject__type=SubjectType.TC,
                observations=AUTO_GENERATED_OBSERVATION,
            ).exists()
        )

    def test_generate_include_tc_false_ignores_tc_hours_for_teacher_capacity(self):
        self.teacher.max_weekly_hours = 5
        self.teacher.save(update_fields=["max_weekly_hours"])

        Subject.objects.create(
            team=self.team,
            name="TC 1A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=self.teacher,
            group=self.group,
        )

        response_with_tc = self.generate_schedule({"include_tc": True})
        self.assert_generate_bad_request_with_detail(
            response_with_tc,
            "exceeds max weekly hours",
        )

        response_without_tc = self.generate_schedule({"include_tc": False})
        self.assertEqual(response_without_tc.status_code, status.HTTP_201_CREATED)

    def test_generate_rejects_invalid_include_tc_value(self):
        response = self.generate_schedule({"include_tc": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertIn("include_tc must be a boolean value", response.data["detail"])

    def test_generate_ignores_tc_capacity_when_include_tc_is_false(self):
        response = self.generate_schedule({"include_tc": False, "tc_capacity": 0})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_generate_rejects_invalid_tc_capacity_when_include_tc_is_true(self):
        response = self.generate_schedule(
            {"include_tc": True, "tc_capacity": "invalid"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertIn("tc_capacity must be an integer value", response.data["detail"])

    def test_generate_response_includes_subject_type_for_generated_sessions(self):
        tc_subject = Subject.objects.create(
            team=self.team,
            name="TC 1A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=self.teacher,
            group=self.group,
        )

        response = self.generate_schedule({"include_tc": True})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        generated_sessions = response.data["schedules"]
        self.assertTrue(generated_sessions)
        self.assertTrue(
            all("subject_type" in session for session in generated_sessions)
        )

        tc_sessions = [
            session
            for session in generated_sessions
            if session["subject"] == tc_subject.id
        ]
        self.assertTrue(tc_sessions)
        self.assertTrue(
            all(session["subject_type"] == SubjectType.TC for session in tc_sessions)
        )
        self.assertTrue(
            any(
                session["subject_type"] == SubjectType.NORMAL
                for session in generated_sessions
            )
        )

    @skipIf(
        schedule_assignment.cp_model is None,
        "Requires OR-Tools CP-SAT to validate tc_capacity constraints.",
    )
    def test_generate_enforces_tc_capacity_per_slot(self):
        teacher_regular = Teacher.objects.create(
            team=self.team,
            name="Profesor Regular",
            max_weekly_hours=20,
            working_hours=12,
        )
        self.subject.weekly_hours = 1
        self.subject.teacher = teacher_regular
        self.subject.save(update_fields=["weekly_hours", "teacher"])

        teacher_2 = Teacher.objects.create(
            team=self.team,
            name="Lucia Martin",
            max_weekly_hours=20,
            working_hours=12,
        )
        group_2 = Group.objects.create(
            name="2A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )

        Subject.objects.create(
            team=self.team,
            name="TC 1A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=self.teacher,
            group=self.group,
            time_preferences={},
        )
        Subject.objects.create(
            team=self.team,
            name="TC 2A",
            weekly_hours=2,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=teacher_2,
            group=group_2,
            time_preferences={},
        )

        response_relaxed_capacity = self.generate_schedule(
            {"include_tc": True, "tc_capacity": 2}
        )
        self.assertEqual(response_relaxed_capacity.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response_relaxed_capacity.data["generation_options"]["tc_capacity"], 2
        )

        tc_schedules = list(
            Schedule.objects.filter(
                subject__type=SubjectType.TC,
                observations=AUTO_GENERATED_OBSERVATION,
            ).order_by("start_time")
        )
        self.assertEqual(len(tc_schedules), 4)

        slot_counts = {}
        for item in tc_schedules:
            slot_counts[item.start_time] = slot_counts.get(item.start_time, 0) + 1

        self.assertTrue(all(count <= 2 for count in slot_counts.values()))

    @skipIf(
        schedule_assignment.cp_model is None,
        "Requires OR-Tools CP-SAT to validate soft constraints.",
    )
    def test_generate_tc_sessions_spread_across_distinct_slots_when_feasible(self):
        self.subject.weekly_hours = 1
        self.subject.save(update_fields=["weekly_hours"])

        teacher_2 = Teacher.objects.create(
            team=self.team,
            name="Lucia Martin",
            max_weekly_hours=20,
            working_hours=12,
        )
        group_2 = Group.objects.create(
            name="2A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )

        Subject.objects.create(
            team=self.team,
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
            team=self.team,
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

    @skipIf(
        schedule_assignment.cp_model is None,
        "Requires OR-Tools CP-SAT to validate soft constraints.",
    )
    def test_generate_tc_prefers_covering_more_real_time_over_preferred_overlap(self):
        self.subject.delete()

        teacher_2 = Teacher.objects.create(
            team=self.team,
            name="Lucia Martin",
            max_weekly_hours=20,
            working_hours=12,
        )
        group_2 = Group.objects.create(
            name="1ESO",
            stage=EducationalStage.SECONDARY,
            team=self.team,
        )
        Classroom.objects.create(name="Aula 1ESO", team=self.team)

        all_slot_keys = set(
            build_slot_preference_index(slots=build_weekly_slots()).values()
        )
        primary_preferences = {
            key: SubjectTimePreferenceState.UNAVAILABLE for key in all_slot_keys
        }
        secondary_preferences = {
            key: SubjectTimePreferenceState.UNAVAILABLE for key in all_slot_keys
        }
        primary_preferences["MON_12:00"] = SubjectTimePreferenceState.PREFER_YES
        primary_preferences["MON_13:00"] = SubjectTimePreferenceState.AVAILABLE
        secondary_preferences["MON_11:30"] = SubjectTimePreferenceState.AVAILABLE
        secondary_preferences["MON_12:30"] = SubjectTimePreferenceState.PREFER_YES

        primary_tc = Subject.objects.create(
            team=self.team,
            name="TC Primaria",
            weekly_hours=1,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.TC,
            teacher=self.teacher,
            group=self.group,
            time_preferences=primary_preferences,
        )
        secondary_tc = Subject.objects.create(
            team=self.team,
            name="TC Secundaria",
            weekly_hours=1,
            duration=1.0,
            preferred_time_slot="Any",
            stage=SubjectEducationalStage.SECONDARY,
            type=SubjectType.TC,
            teacher=teacher_2,
            group=group_2,
            time_preferences=secondary_preferences,
        )

        response = self.generate_schedule({"include_tc": True, "tc_capacity": 2})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tc_schedules = list(
            Schedule.objects.filter(subject__in=[primary_tc, secondary_tc]).order_by(
                "start_time"
            )
        )
        self.assertEqual(len(tc_schedules), 2)

        assigned_keys = {
            slot_preference_key_from_datetime(slot=item.start_time)
            for item in tc_schedules
        }
        self.assertEqual(assigned_keys, {"MON_11:30", "MON_13:00"})

    def test_generate_assigns_only_subject_allowed_classrooms(self):
        self.classroom.is_shared = True
        self.classroom.save(update_fields=["is_shared"])
        assigned = Classroom.objects.create(
            name="Aula Asignada",
            is_shared=True,
            team=self.team,
        )
        self.subject.allowed_classrooms.set([assigned])

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        generated_classroom_ids = set(
            Schedule.objects.filter(subject=self.subject).values_list(
                "classroom_id", flat=True
            )
        )
        self.assertEqual(generated_classroom_ids, {assigned.id})

    def test_generate_prefers_shared_when_allowed_contains_mixed_rooms(self):
        self.classroom.name = "Aula 1A"
        self.classroom.is_shared = False
        self.classroom.save(update_fields=["name", "is_shared"])
        music_room = Classroom.objects.create(
            name="Aula de Musica",
            is_shared=True,
            team=self.team,
        )
        self.subject.allowed_classrooms.set([self.classroom, music_room])

        response = self.generate_schedule()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        generated_classroom_ids = set(
            Schedule.objects.filter(subject=self.subject).values_list(
                "classroom_id", flat=True
            )
        )
        self.assertEqual(generated_classroom_ids, {music_room.id})

    def test_generate_uses_any_classroom_when_subject_has_no_restrictions(self):
        self.classroom.is_shared = True
        self.classroom.save(update_fields=["is_shared"])

        response = self.generate_schedule()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        generated_classroom_ids = set(
            Schedule.objects.filter(subject=self.subject).values_list(
                "classroom_id", flat=True
            )
        )
        self.assertIn(self.classroom.id, generated_classroom_ids)

    def test_generate_spreads_sessions_when_one_allowed_classroom_is_shared(self):
        self.classroom.is_shared = True
        self.classroom.save(update_fields=["is_shared"])
        self.subject.weekly_hours = 1
        self.subject.save(update_fields=["weekly_hours"])

        teacher_2 = Teacher.objects.create(
            team=self.team,
            name="Elena Ruiz",
            max_weekly_hours=20,
            working_hours=8,
        )
        group_2 = Group.objects.create(
            name="2A",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        other_subject = Subject.objects.create(
            team=self.team,
            name="Science",
            weekly_hours=1,
            duration=1.0,
            preferred_time_slot="Morning",
            stage=SubjectEducationalStage.PRIMARY,
            type=SubjectType.NORMAL,
            teacher=teacher_2,
            group=group_2,
        )
        self.subject.allowed_classrooms.set([self.classroom])
        other_subject.allowed_classrooms.set([self.classroom])

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
            "Two sessions that share a single classroom must not overlap.",
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
        # For PRIMARY stage, allow only 3 Monday slots: 09:00, 12:00 and 13:00.
        # With weekly_hours=2 the solver must pick exactly 2 of those 3 slots.
        # Compact choice (12:00 + 13:00) yields 0 internal gaps, while any pair
        # that includes 09:00 creates an internal gap -> F-29 should avoid it.
        slot_pref_index = build_slot_preference_index(slots=build_weekly_slots())
        allowed = {"MON_09:00", "MON_12:00", "MON_13:00"}
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
        # The compact pair should win; MON_09:00 (far from 12:00/13:00) must not appear.
        self.assertNotIn(
            "MON_09:00",
            assigned_keys,
            "Expected compact assignment (MON_12:00 + MON_13:00) but got a fragmented one.",
        )

    def test_generate_rejects_group_intraday_gaps(self):
        """F-30: a group's timetable cannot contain intra-day gaps."""
        self.subject.weekly_hours = 1
        self.subject.save(update_fields=["weekly_hours"])

        teacher_2 = Teacher.objects.create(
            team=self.team,
            name="Lucia Lopez",
            max_weekly_hours=20,
            working_hours=8,
        )
        Subject.objects.create(
            team=self.team,
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
