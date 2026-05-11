from datetime import timedelta
from unittest import skipIf

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from auditableEntity.models import AuditableEntity, AuditActionType, AuditEntry
from classroom.models import Classroom
from common.export_utils import REPORTLAB_AVAILABLE
from common.test_utils import AuthenticatedAdminAPIMixin
from group.models import EducationalStage as GroupEducationalStage
from group.models import Group
from namedEntity.models import NamedEntity
from schedule.models import Schedule
from subject.models import Subject, SubjectType
from teacher.models import Teacher
from user.models import CollaborationTeam


class AuditableEntityTests(SimpleTestCase):
    def test_auditable_entity_inherits_named_entity(self):
        self.assertTrue(issubclass(AuditableEntity, NamedEntity))

    def test_auditable_entity_has_audit_fields(self):
        field_names = {field.name for field in AuditableEntity._meta.get_fields()}

        self.assertIn("created_at", field_names)
        self.assertIn("updated_at", field_names)
        self.assertIn("created_by", field_names)
        self.assertIn("updated_by", field_names)


class AuditEntryApiTests(AuthenticatedAdminAPIMixin, APITestCase):
    def setUp(self):
        self.authenticate_admin(email_prefix="audit-api")
        self.team_user = self.create_user(
            email="audit-direccion@test.com",
            given_name="Direccion",
            family_name="Audit",
        )
        self.outside_user, self.outside_team = self.create_isolated_user(
            email_prefix="audit-outsider"
        )
        self.team = CollaborationTeam.objects.create(name="Equipo Auditoria")
        self.team.members.set([self.user, self.team_user])
        self.user.active_team = self.team
        self.user.save(update_fields=["active_team"])
        self.teacher = Teacher.objects.create(
            name="Audit Teacher",
            max_weekly_hours=20,
            working_hours=10,
            team=self.team,
        )
        self.classroom = Classroom.objects.create(
            name="Audit Classroom", team=self.team
        )
        self.group = Group.objects.create(
            name="Audit Group",
            stage=GroupEducationalStage.PRIMARY,
            team=self.team,
        )
        self.subject = Subject.objects.create(
            name="Audit Subject",
            weekly_hours=2,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
            team=self.team,
        )
        AuditEntry.objects.all().delete()

    def create_schedule(self):
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        schedule = Schedule.objects.create(
            name="Audit Schedule",
            start_time=start_time,
            end_time=end_time,
            observations="Initial",
            team=self.team,
            teacher=self.teacher,
            classroom=self.classroom,
            group=self.group,
            subject=self.subject,
            created_by=self.user.email,
            updated_by=self.user.email,
        )
        schedule.users.add(self.user)
        AuditEntry.objects.all().delete()
        return schedule

    def test_create_teacher_generates_audit_entry(self):
        response = self.client.post(
            reverse("teacher-list"),
            {
                "name": "Ana Auditoria",
                "max_weekly_hours": 22,
                "working_hours": 14,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = AuditEntry.objects.get(
            entity_type="teacher", entity_id=response.data["id"]
        )
        self.assertEqual(entry.action_type, AuditActionType.CREATE)
        self.assertEqual(entry.actor_name, self.user.get_full_name())
        self.assertEqual(entry.changed_fields[0]["campo"], "Nombre")
        self.assertIn("Se creó el profesor", entry.detail)

    def test_delete_group_preserves_audit_entry_after_entity_is_removed(self):
        group = Group.objects.create(
            name="Delete Me",
            stage=GroupEducationalStage.SECONDARY,
            team=self.team,
        )
        AuditEntry.objects.all().delete()

        response = self.client.delete(reverse("group-detail", args=[group.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Group.objects.filter(id=group.id).exists())
        entry = AuditEntry.objects.get(entity_type="group", entity_id=group.id)
        self.assertEqual(entry.action_type, AuditActionType.DELETE)
        self.assertEqual(entry.entity_name, "Delete Me")
        self.assertEqual(entry.actor_name, self.user.get_full_name())

    def test_schedule_users_m2m_change_is_audited(self):
        schedule = self.create_schedule()

        response = self.client.patch(
            reverse("schedule-detail", args=[schedule.id]),
            {"users": [self.user.id, self.team_user.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry = AuditEntry.objects.filter(entity_type="schedule").latest("id")
        self.assertEqual(entry.entity_id, schedule.id)
        self.assertEqual(entry.changed_fields[0]["campo"], "Usuarios")
        self.assertEqual(
            entry.changed_fields[0]["valor_nuevo"],
            sorted([self.user.get_full_name(), self.team_user.get_full_name()]),
        )

    def test_subject_mandatory_classroom_change_is_audited(self):
        classroom = Classroom.objects.create(name="Lab 2", team=self.team)
        AuditEntry.objects.all().delete()

        response = self.client.patch(
            reverse("subject-detail", args=[self.subject.id]),
            {
                "mandatory_classroom": classroom.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry = AuditEntry.objects.filter(entity_type="subject").latest("id")
        self.assertEqual(entry.entity_id, self.subject.id)
        campo_names = [f["campo"] for f in entry.changed_fields]
        self.assertIn("Aula", campo_names)

    def test_update_teacher_stores_previous_and_new_values(self):
        teacher = Teacher.objects.create(
            name="Laura Inicial",
            max_weekly_hours=18,
            working_hours=9,
            team=self.team,
        )
        AuditEntry.objects.all().delete()

        response = self.client.patch(
            reverse("teacher-detail", args=[teacher.id]),
            {"name": "Laura Final", "max_weekly_hours": 20},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry = AuditEntry.objects.filter(entity_type="teacher").latest("id")
        self.assertEqual(entry.action_type, AuditActionType.UPDATE)
        self.assertEqual(
            entry.changed_fields,
            [
                {
                    "campo": "Nombre",
                    "valor_anterior": "Laura Inicial",
                    "valor_nuevo": "Laura Final",
                },
                {
                    "campo": "Máximo de horas semanales",
                    "valor_anterior": 18,
                    "valor_nuevo": 20,
                },
            ],
        )

    def test_audit_entries_endpoint_filters_by_entity_type_and_action_in_spanish(self):
        self.client.post(
            reverse("teacher-list"),
            {
                "name": "Teacher Filter",
                "max_weekly_hours": 18,
                "working_hours": 12,
            },
            format="json",
        )
        self.client.post(
            reverse("classroom-list"),
            {"name": "Classroom Filter"},
            format="json",
        )

        response = self.client.get(
            reverse("auditentry-list"),
            {"tipo_entidad": "profesor", "tipo_accion": "creación"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 1)
        self.assertTrue(
            all(item["tipo_entidad"] == "Profesor" for item in response.data["results"])
        )
        self.assertTrue(
            all(item["tipo_accion"] == "Creación" for item in response.data["results"])
        )

    def test_audit_entries_endpoint_only_shows_current_user_and_team(self):
        AuditEntry.objects.create(
            entity_type="teacher",
            entity_id=1,
            entity_name="Entrada propia",
            action_type=AuditActionType.CREATE,
            detail='Se creo el profesor "Entrada propia".',
            actor=self.user,
            actor_name=self.user.get_full_name(),
            team=self.team,
        )
        AuditEntry.objects.create(
            entity_type="teacher",
            entity_id=2,
            entity_name="Entrada equipo",
            action_type=AuditActionType.CREATE,
            detail='Se creo el profesor "Entrada equipo".',
            actor=self.team_user,
            actor_name=self.team_user.get_full_name(),
            team=self.team,
        )
        AuditEntry.objects.create(
            entity_type="teacher",
            entity_id=3,
            entity_name="Entrada externa",
            action_type=AuditActionType.CREATE,
            detail='Se creo el profesor "Entrada externa".',
            actor=self.outside_user,
            actor_name=self.outside_user.get_full_name(),
            team=self.outside_team,
        )

        response = self.client.get(reverse("auditentry-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["nombre_entidad"] for item in response.data["results"]]
        self.assertIn("Entrada propia", names)
        self.assertIn("Entrada equipo", names)
        self.assertNotIn("Entrada externa", names)

    def test_audit_filter_users_endpoint_only_returns_current_user_and_team(self):
        response = self.client.get(reverse("auditentry-filter-users"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data}
        self.assertIn(self.user.id, returned_ids)
        self.assertIn(self.team_user.id, returned_ids)
        self.assertNotIn(self.outside_user.id, returned_ids)

    def test_audit_entries_endpoint_allows_direccion_in_same_team(self):
        AuditEntry.objects.create(
            entity_type="teacher",
            entity_id=999,
            entity_name="Existing Audit",
            action_type=AuditActionType.CREATE,
            detail='Se creo el profesor "Existing Audit".',
            actor=self.user,
            actor_name=self.user.get_full_name(),
            team=self.team,
        )
        self.client.force_authenticate(self.team_user)

        response = self.client.get(reverse("auditentry-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_audit_entries_endpoint_allows_any_authenticated_user(self):
        AuditEntry.objects.create(
            entity_type="teacher",
            entity_id=21,
            entity_name="Entrada externa propia",
            action_type=AuditActionType.CREATE,
            detail='Se creo el profesor "Entrada externa propia".',
            actor=self.outside_user,
            actor_name=self.outside_user.get_full_name(),
            team=self.outside_team,
        )
        self.client.force_authenticate(self.outside_user)

        response = self.client.get(reverse("auditentry-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["nombre_entidad"], "Entrada externa propia"
        )

    def test_audit_entries_endpoint_rejects_user_filter_outside_team(self):
        response = self.client.get(
            reverse("auditentry-list"),
            {"usuario_id": self.outside_user.id},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("usuario_id", response.data)

    def test_audit_entries_export_csv_applies_filters(self):
        now = timezone.now()
        own_entry = AuditEntry.objects.create(
            entity_type="teacher",
            entity_id=31,
            entity_name="Profesor exportable",
            action_type=AuditActionType.CREATE,
            detail='Se creó el profesor "Profesor exportable".',
            changed_fields=[
                {
                    "campo": "Preferencias horarias",
                    "valor_nuevo": {
                        "MON_09:30": "PREFER_YES",
                        "MON_10:30": "AVAILABLE",
                        "FRI_12:00": "PREFER_NO",
                        "FRI_14:00": "UNAVAILABLE",
                    },
                }
            ],
            actor=self.user,
            actor_name=self.user.get_full_name(),
            team=self.team,
        )
        own_entry.occurred_at = now
        own_entry.save(update_fields=["occurred_at"])
        AuditEntry.objects.create(
            entity_type="classroom",
            entity_id=32,
            entity_name="Aula descartada",
            action_type=AuditActionType.UPDATE,
            detail='Se modificó el aula "Aula descartada".',
            actor=self.user,
            actor_name=self.user.get_full_name(),
            team=self.team,
        )

        response = self.client.get(
            reverse("auditentry-export"),
            {
                "export_format": "csv",
                "tipo_entidad": "profesor",
                "tipo_accion": "creación",
                "usuario_id": self.user.id,
                "fecha_desde": now.date().isoformat(),
                "columns": "Fecha",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn('filename="orarioo_audit_', response["Content-Disposition"])
        csv_text = response.content.decode("utf-8-sig")
        self.assertIn(f"'{now.strftime('%d/%m/%Y')}", csv_text)
        self.assertIn("Profesor exportable", csv_text)
        self.assertNotIn("Aula descartada", csv_text)
        self.assertIn("Preferidas: Lunes a las 09:30.", csv_text)
        self.assertIn("Disponibles: Lunes a las 10:30.", csv_text)

    @skipIf(not REPORTLAB_AVAILABLE, "reportlab is not installed")
    def test_audit_entries_export_pdf_returns_pdf(self):
        AuditEntry.objects.create(
            entity_type="group",
            entity_id=40,
            entity_name="Grupo PDF",
            action_type=AuditActionType.DELETE,
            detail='Se eliminó el grupo "Grupo PDF".',
            actor=self.user,
            actor_name=self.user.get_full_name(),
            team=self.team,
        )

        response = self.client.get(
            reverse("auditentry-export"),
            {"export_format": "pdf"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="orarioo_audit_', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
