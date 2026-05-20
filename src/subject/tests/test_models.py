"""Tests for Subject.clean() field constraints.

Patterns: Boundary Value Analysis (duration > 0, weekly_hours > 0),
          Equivalence Partitioning (valid/invalid classes), AAA.
Uses Django TestCase (DB needed for FK dependencies).
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from common.stages import GroupEducationalStage
from group.models import Group
from subject.models import Subject
from teacher.models import Teacher
from user.models import CollaborationTeam


class SubjectCleanTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.team = CollaborationTeam.objects.create(name="Test Team Subjects")
        cls.teacher = Teacher.objects.create(
            name="Subject Teacher",
            max_weekly_hours=10,
            max_weekly_minutes=0,
            team=cls.team,
        )
        cls.group = Group.objects.create(
            name="Subject Group",
            stage=GroupEducationalStage.PRIMARY,
            team=cls.team,
        )

    def _make(self, **kwargs):
        defaults = {
            "name": "Test Subject",
            "weekly_hours": 5,
            "duration": 1.0,
            "teacher": self.teacher,
            "group": self.group,
            "team": self.team,
        }
        defaults.update(kwargs)
        return Subject(**defaults)

    # ── duration BVA ──────────────────────────────────────────────────────

    def test_duration_positive_is_valid(self):
        """EP valid: any positive duration must be accepted."""
        self._make(duration=1.0).clean()

    def test_duration_zero_raises(self):
        """BVA lower bound: duration=0 must raise for the duration field."""
        with self.assertRaises(ValidationError) as ctx:
            self._make(duration=0.0).clean()
        self.assertIn(
            "duration",
            ctx.exception.message_dict,
            "duration=0 must target the duration field",
        )

    def test_duration_negative_raises(self):
        """EP invalid: negative duration must raise."""
        with self.assertRaises(ValidationError):
            self._make(duration=-1.0).clean()

    def test_duration_very_negative_raises(self):
        """EP invalid: large negative duration must raise."""
        with self.assertRaises(ValidationError):
            self._make(duration=-100.0).clean()

    def test_duration_epsilon_above_zero_is_valid(self):
        """BVA: smallest positive float must pass (duration just above the boundary)."""
        self._make(duration=0.001).clean()

    def test_duration_two_is_valid(self):
        """EP valid: double-length session (duration=2.0) must be accepted."""
        self._make(duration=2.0).clean()

    # ── weekly_hours BVA ──────────────────────────────────────────────────

    def test_weekly_hours_one_is_valid(self):
        """BVA lower valid bound: weekly_hours=1 must be accepted."""
        self._make(weekly_hours=1).clean()

    def test_weekly_hours_zero_raises(self):
        """BVA: weekly_hours=0 must raise for the weekly_hours field."""
        with self.assertRaises(ValidationError) as ctx:
            self._make(weekly_hours=0).clean()
        self.assertIn(
            "weekly_hours",
            ctx.exception.message_dict,
            "weekly_hours=0 must target the weekly_hours field",
        )

    def test_weekly_hours_large_value_is_valid(self):
        """EP valid: large (but positive) weekly_hours must be accepted."""
        self._make(weekly_hours=30).clean()
