"""Tests for schedule.algorithm.constraints.hard capacity validators.

Covers: group_daily_limit, group_weekly_limit, validate_group_and_teacher_capacity.
Patterns: Equivalence Partitioning (valid/invalid load), Boundary Value Analysis
(exactly at limit, one over limit), Arrange-Act-Assert.
No database access — all objects are SimpleNamespace stubs.
"""

from django.test import SimpleTestCase

from schedule.algorithm.constraints.hard import (
    group_daily_limit, group_weekly_limit, validate_group_and_teacher_capacity)
from schedule.algorithm.errors import (ScheduleCapacityError,
                                       ScheduleGenerationError)
from schedule.tests.algorithm.factories import (make_group_stub, make_session,
                                                make_teacher_stub,
                                                make_week_slots)


class GroupLimitsTest(SimpleTestCase):
    """EP: preschool/primary stage class vs. secondary/alevels class."""

    def test_preschool_daily_limit_is_5(self):
        """Preschool groups may have at most 5 sessions per day."""
        self.assertEqual(group_daily_limit(make_group_stub(stage="preschool")), 5)

    def test_primary_daily_limit_is_5(self):
        """Primary groups may have at most 5 sessions per day."""
        self.assertEqual(group_daily_limit(make_group_stub(stage="primary")), 5)

    def test_secondary_daily_limit_is_6(self):
        """Secondary groups may have at most 6 sessions per day."""
        self.assertEqual(group_daily_limit(make_group_stub(stage="secondary")), 6)

    def test_alevels_daily_limit_is_6(self):
        """A-Levels groups share the secondary daily limit of 6."""
        self.assertEqual(group_daily_limit(make_group_stub(stage="alevels")), 6)

    def test_primary_weekly_limit_is_25(self):
        """Primary groups may have at most 25 weekly sessions."""
        self.assertEqual(group_weekly_limit(make_group_stub(stage="primary")), 25)

    def test_secondary_weekly_limit_is_30(self):
        """Secondary groups may have at most 30 weekly sessions."""
        self.assertEqual(group_weekly_limit(make_group_stub(stage="secondary")), 30)


class ValidateGroupSlotCapacityTest(SimpleTestCase):
    """BVA: sessions == slots (ok), sessions > slots (error)."""

    def _make_slots(self, count):
        """Return exactly count non-recess slots."""
        return make_week_slots(hours_per_day=[9, 10, 11, 13, 14])[:count]

    def test_sessions_equal_slot_count_passes(self):
        """Exactly as many sessions as available slots must not raise."""
        slots = self._make_slots(5)
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=20)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(5)]
        validate_group_and_teacher_capacity(sessions=sessions, slots=slots)

    def test_one_session_over_slot_count_raises(self):
        """One more session than slots must raise ScheduleGenerationError."""
        slots = self._make_slots(4)
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=20)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(5)]
        with self.assertRaises(
            ScheduleGenerationError, msg="Sessions > slots must raise"
        ):
            validate_group_and_teacher_capacity(sessions=sessions, slots=slots)


class ValidateGroupWeeklyCapacityTest(SimpleTestCase):
    """BVA around the 25-session PRIMARY weekly limit and 30-session SECONDARY limit."""

    def _make_big_slots(self):
        """Return 35 slots to remove slot-count as a confound."""
        return make_week_slots(hours_per_day=[8, 9, 10, 11, 12, 13, 14])

    def test_primary_at_limit_passes(self):
        """25 sessions for a PRIMARY group (exactly at limit) must not raise."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=30)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(25)]
        validate_group_and_teacher_capacity(sessions=sessions, slots=slots)

    def test_primary_one_over_limit_raises_capacity_error(self):
        """26 sessions for a PRIMARY group (one over limit) must raise ScheduleCapacityError."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=30)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(26)]
        with self.assertRaises(
            ScheduleCapacityError,
            msg="26 sessions for PRIMARY must exceed 25-session weekly limit",
        ):
            validate_group_and_teacher_capacity(sessions=sessions, slots=slots)

    def test_secondary_at_limit_passes(self):
        """30 sessions for a SECONDARY group (exactly at limit) must not raise."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="secondary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=35)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(30)]
        validate_group_and_teacher_capacity(sessions=sessions, slots=slots)

    def test_secondary_one_over_limit_raises(self):
        """31 sessions for a SECONDARY group must raise ScheduleCapacityError."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="secondary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=35)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(31)]
        with self.assertRaises(ScheduleCapacityError):
            validate_group_and_teacher_capacity(sessions=sessions, slots=slots)


class ValidateTeacherWeeklyCapacityTest(SimpleTestCase):
    """BVA around teacher max_weekly_hours and the 30-minute extra allowance."""

    def _make_big_slots(self):
        return make_week_slots(hours_per_day=[8, 9, 10, 11, 12, 13, 14])

    def test_teacher_at_max_hours_passes(self):
        """Teacher with max=2h assigned 2 sessions must not raise."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=2, max_weekly_minutes=0)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(2)]
        validate_group_and_teacher_capacity(sessions=sessions, slots=slots)

    def test_teacher_one_over_max_raises(self):
        """Teacher with max=2h assigned 3 sessions must raise ScheduleCapacityError."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=2, max_weekly_minutes=0)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(3)]
        with self.assertRaises(
            ScheduleCapacityError,
            msg="3 sessions with max=2h must exceed teacher capacity",
        ):
            validate_group_and_teacher_capacity(sessions=sessions, slots=slots)

    def test_teacher_with_30_extra_minutes_allows_fractional(self):
        """Teacher max=1h30m (1h + 30min) allows 1 session but not 2."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=1, max_weekly_minutes=30)

        # 1 session = 1.0h ≤ 1.5h → should pass
        sessions_ok = [make_session(group=group, teacher=teacher)]
        validate_group_and_teacher_capacity(sessions=sessions_ok, slots=slots)

        # 2 sessions = 2.0h > 1.5h → should fail
        sessions_over = [make_session(group=group, teacher=teacher) for _ in range(2)]
        with self.assertRaises(
            ScheduleCapacityError,
            msg="2 sessions with max=1h30m must raise (2h > 1.5h limit)",
        ):
            validate_group_and_teacher_capacity(sessions=sessions_over, slots=slots)

    def test_error_message_mentions_teacher(self):
        """ScheduleCapacityError for teacher overload must reference resource_type='teacher'."""
        slots = self._make_big_slots()
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, name="Prof. X", max_weekly_hours=1)
        sessions = [make_session(group=group, teacher=teacher) for _ in range(2)]
        with self.assertRaises(ScheduleCapacityError) as ctx:
            validate_group_and_teacher_capacity(sessions=sessions, slots=slots)
        self.assertEqual(
            ctx.exception.context.get("resource_type"),
            "teacher",
            "Capacity error for teacher overload must have context resource_type='teacher'",
        )
