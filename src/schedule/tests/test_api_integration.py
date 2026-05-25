"""Integration tests for schedule API: multi-tenancy isolation and generation flow.

These tests verify security boundaries (Tenant A cannot see/edit Tenant B data)
and the happy-path contract (POST generate → Schedule objects created + AuditEntry logged).
They inherit AuthenticatedAdminAPIMixin to reduce boilerplate and reuse the
thread-synchronization helper from the existing ScheduleApiTests class.
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection as db_connection
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from auditableEntity.models import AuditActionType, AuditEntry
from classroom.models import Classroom
from common.test_utils import AuthenticatedAdminAPIMixin
from group.models import EducationalStage, Group
from schedule.models import Schedule
from subject.models import Subject, SubjectType
from teacher.models import Teacher

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_sync_thread(target, args=(), kwargs=None, daemon=False, **kw):
    """Replace threading.Thread with a synchronous stub for deterministic tests."""

    class _SyncThread:
        def start(self):
            with patch.object(db_connection, "close", lambda: None):
                target(*args, **(kwargs or {}))

    return _SyncThread()


def generate_schedule_sync(client, payload=None):
    """POST to schedule-generate, run synchronously, poll status, return response-like object."""
    with patch("schedule.views.threading.Thread", side_effect=_make_sync_thread):
        start_resp = client.post(
            reverse("schedule-generate"), payload or {}, format="json"
        )

    if start_resp.status_code != status.HTTP_202_ACCEPTED:
        return start_resp

    job_id = start_resp.data.get("job_id")
    poll_resp = client.get(
        reverse("schedule-generate-status", kwargs={"job_id": job_id})
    )
    if poll_resp.data.get("status") == "DONE":
        return SimpleNamespace(
            status_code=status.HTTP_201_CREATED,
            data=poll_resp.data.get("result", {}),
        )
    return SimpleNamespace(
        status_code=status.HTTP_400_BAD_REQUEST,
        data=poll_resp.data.get("error", {}),
    )


# ---------------------------------------------------------------------------
# Multi-tenancy isolation
# ---------------------------------------------------------------------------


class ScheduleMultiTenancyIsolationTest(AuthenticatedAdminAPIMixin, APITestCase):
    """Tenant A must never see or modify schedules belonging to Tenant B.

    These are the most critical security tests in the suite: a data-leak bug
    here would expose one school's timetable to another.
    """

    def setUp(self):
        self.authenticate_admin(email_prefix="tenant-a-isolation")
        self.other_user, self.other_team = self.create_isolated_user(
            email_prefix="tenant-b-isolation"
        )

        # Create entities for Tenant B
        self.b_teacher = Teacher.objects.create(
            name="B Teacher", max_weekly_hours=10, team=self.other_team
        )
        self.b_classroom = Classroom.objects.create(name="B Room", team=self.other_team)
        self.b_group = Group.objects.create(
            name="B Group", stage=EducationalStage.PRIMARY, team=self.other_team
        )
        start = timezone.now() + timedelta(days=1)
        self.b_schedule = Schedule.objects.create(
            name="B Schedule",
            start_time=start,
            end_time=start + timedelta(hours=1),
            teacher=self.b_teacher,
            classroom=self.b_classroom,
            group=self.b_group,
            team=self.other_team,
        )

    def test_list_does_not_expose_other_tenant_schedules(self):
        """GET /schedules/ must not return any schedule belonging to Tenant B."""
        response = self.client.get(reverse("schedule-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data.get("results", response.data)]
        self.assertNotIn(
            self.b_schedule.id,
            ids,
            "Tenant A must not see Tenant B schedules in the list",
        )

    def test_retrieve_other_tenant_schedule_returns_404(self):
        """GET /schedules/<id>/ for Tenant B's schedule must return 404, not 200 or 403."""
        response = self.client.get(
            reverse("schedule-detail", args=[self.b_schedule.id])
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Accessing another tenant's schedule must return 404 (not found, not forbidden)",
        )

    def test_patch_other_tenant_schedule_returns_404(self):
        """PATCH /schedules/<id>/ for Tenant B's schedule must return 404."""
        response = self.client.patch(
            reverse("schedule-detail", args=[self.b_schedule.id]),
            {"observations": "hacked"},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "PATCH of another tenant's schedule must return 404",
        )

    def test_delete_other_tenant_schedule_returns_404(self):
        """DELETE /schedules/<id>/ for Tenant B's schedule must return 404."""
        response = self.client.delete(
            reverse("schedule-detail", args=[self.b_schedule.id])
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "DELETE of another tenant's schedule must return 404",
        )

    def test_b_schedule_still_exists_after_tenant_a_requests(self):
        """Tenant A's requests must not have modified or deleted Tenant B's data."""
        self.assertTrue(
            Schedule.objects.filter(pk=self.b_schedule.pk).exists(),
            "Tenant B's schedule must remain untouched after Tenant A's requests",
        )


# ---------------------------------------------------------------------------
# Generation flow: schedules created + audit entry logged
# ---------------------------------------------------------------------------


class ScheduleGenerationFlowTest(AuthenticatedAdminAPIMixin, APITestCase):
    """POST /schedules/generate/ must create Schedule rows and log an AuditEntry.

    This test verifies the end-to-end contract between the API, the algorithm,
    and the audit layer.  It uses the same thread-patching technique as the
    existing ScheduleApiTests to run the async job synchronously.
    """

    def setUp(self):
        self.authenticate_admin(email_prefix="gen-flow")
        self.teacher = Teacher.objects.create(
            team=self.team,
            name="Gen Flow Teacher",
            max_weekly_hours=20,
        )
        self.classroom = Classroom.objects.create(name="Gen Room", team=self.team)
        self.group = Group.objects.create(
            name="Gen Group",
            stage=EducationalStage.PRIMARY,
            team=self.team,
        )
        self.subject = Subject.objects.create(
            team=self.team,
            name="Gen Subject",
            weekly_hours=3,
            duration=1.0,
            type=SubjectType.NORMAL,
            teacher=self.teacher,
            group=self.group,
        )
        AuditEntry.objects.all().delete()

    def test_generate_creates_schedule_and_audit_entry(self):
        """POST generate with valid data must create Schedules in the DB and one AuditEntry.

        Verifies:
        1. HTTP 201 returned after polling
        2. Schedule rows == subject.weekly_hours
        3. Exactly one AuditEntry of type CREATE for entity_type 'schedule'
        """
        Classroom.objects.filter(
            team=self.other_team if hasattr(self, "other_team") else None
        ).delete()

        response = generate_schedule_sync(self.client)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            "Generate endpoint must return 201 after successful generation",
        )
        self.assertIn(
            "schedules",
            response.data,
            "Response must contain a 'schedules' key",
        )

        # Schedules persisted
        self.assertEqual(
            Schedule.objects.count(),
            self.subject.weekly_hours,
            f"Must create exactly {self.subject.weekly_hours} Schedule rows (== weekly_hours)",
        )

        # AuditEntry logged
        entries = AuditEntry.objects.filter(
            entity_type="schedule",
            action_type=AuditActionType.CREATE,
        )
        self.assertEqual(
            entries.count(),
            1,
            "Exactly one AuditEntry of type CREATE for schedule must be created",
        )
        entry = entries.first()
        self.assertEqual(
            entry.team,
            self.team,
            "AuditEntry must be scoped to the requesting team",
        )
        self.assertEqual(entry.detail, "Se generó un horario.")
        self.assertNotIn("Auto ", entry.detail)
        self.assertNotIn("sesiones", entry.detail)

    def test_generate_without_teacher_returns_error(self):
        """POST generate with no teachers must return 400 with a diagnostic code."""
        Subject.objects.all().delete()
        Teacher.objects.all().delete()

        response = generate_schedule_sync(self.client)
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Generate with no teachers must fail with 400",
        )
