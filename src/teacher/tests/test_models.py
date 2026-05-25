"""Tests for Teacher.clean() field constraints.

Patterns: Boundary Value Analysis (minutes ∈ {0,30}),
          Equivalence Partitioning (valid/invalid classes), AAA.
Uses Django TestCase (DB needed to build CollaborationTeam FK).
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from teacher.models import Teacher
from user.models import CollaborationTeam


class TeacherCleanTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.team = CollaborationTeam.objects.create(name="Test Team Teachers")

    def _make(self, **kwargs):
        defaults = {
            "name": "Test Teacher",
            "max_weekly_hours": 10,
            "max_weekly_minutes": 0,
            "team": self.team,
        }
        defaults.update(kwargs)
        return Teacher(**defaults)

    # ── max_weekly_minutes BVA ─────────────────────────────────────────────

    def test_minutes_0_is_valid(self):
        """BVA lower bound: 0 minutes must be accepted."""
        self._make(max_weekly_minutes=0).clean()

    def test_minutes_30_is_valid(self):
        """BVA upper valid value: 30 minutes must be accepted."""
        self._make(max_weekly_minutes=30).clean()

    def test_minutes_1_is_invalid(self):
        """BVA: 1 minute is not in {0, 30} → must raise for max_weekly_minutes field."""
        with self.assertRaises(ValidationError) as ctx:
            self._make(max_weekly_minutes=1).clean()
        self.assertIn(
            "max_weekly_minutes",
            ctx.exception.message_dict,
            "Validation error must target the max_weekly_minutes field",
        )

    def test_minutes_29_is_invalid(self):
        """BVA: 29 minutes (one below 30) must raise."""
        with self.assertRaises(ValidationError):
            self._make(max_weekly_minutes=29).clean()

    def test_minutes_31_is_invalid(self):
        """BVA: 31 minutes (one above 30) must raise."""
        with self.assertRaises(ValidationError):
            self._make(max_weekly_minutes=31).clean()

    def test_minutes_15_is_invalid(self):
        """EP invalid class: arbitrary non-zero non-30 value must raise."""
        with self.assertRaises(ValidationError):
            self._make(max_weekly_minutes=15).clean()

    # ── zero total load ────────────────────────────────────────────────────

    def test_zero_hours_zero_minutes_raises(self):
        """EP: 0h + 0m = zero total weekly load must raise for max_weekly_hours."""
        with self.assertRaises(ValidationError) as ctx:
            self._make(max_weekly_hours=0, max_weekly_minutes=0).clean()
        self.assertIn(
            "max_weekly_hours",
            ctx.exception.message_dict,
            "Zero total load must target the max_weekly_hours field",
        )

    def test_zero_hours_thirty_minutes_is_valid(self):
        """EP valid: 0h + 30m is a non-zero total → must not raise."""
        self._make(max_weekly_hours=0, max_weekly_minutes=30).clean()

    def test_one_hour_zero_minutes_is_valid(self):
        """EP valid: any positive hours value must pass."""
        self._make(max_weekly_hours=1, max_weekly_minutes=0).clean()

    def test_team_is_required_by_database(self):
        """A teacher cannot be persisted outside a collaboration team."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            Teacher.objects.create(
                name="No Team Teacher",
                max_weekly_hours=10,
                max_weekly_minutes=0,
                team=None,
            )
