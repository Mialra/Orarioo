"""Tests for schedule.algorithm.tc_assigner internal helpers.

Covers: _build_unique_tc_slots, _overlaps_any, _is_dead_gap, _compute_exact_hours_deficit.
The public assign_tc_sessions is an integration-level function requiring DB; only
the pure-Python helpers are unit-tested here.
Patterns: EP (gap/no-gap, overlap/no-overlap), BVA (boundary times), AAA.
No database access.
"""

from datetime import time

from django.test import SimpleTestCase

from schedule.algorithm.tc_assigner import (_build_unique_tc_slots,
                                            _compute_exact_hours_deficit,
                                            _is_dead_gap, _overlaps_any)
from schedule.tests.algorithm.factories import (make_slot, make_teacher_stub,
                                                make_week_slots)


class BuildUniqueTcSlotsTest(SimpleTestCase):
    """EP: recess slots excluded, 30-min slots excluded, duplicates across stages merged."""

    def test_excludes_recess_slots(self):
        """Slots with is_recess=True must never appear in TC slot list."""
        slots = make_week_slots(hours_per_day=[9, 10], include_recess=True)
        tc_slots = _build_unique_tc_slots(slots)
        # All TC slots must be exactly 60 minutes (recess is 30 min)
        for slot in tc_slots:
            start_m = slot["start_time"].hour * 60 + slot["start_time"].minute
            end_m = slot["end_time"].hour * 60 + slot["end_time"].minute
            self.assertEqual(
                end_m - start_m,
                60,
                "All TC slots must be exactly 60 minutes (recess excluded)",
            )

    def test_deduplicates_same_time_across_stages(self):
        """The same (weekday, start_time) appearing in two stages must produce one TC slot."""
        slots = [
            make_slot(day_offset=0, hour=9, stage="primary"),
            make_slot(day_offset=0, hour=9, stage="secondary"),
            make_slot(day_offset=0, hour=10, stage="primary"),
        ]
        tc_slots = _build_unique_tc_slots(slots)
        mon_9_slots = [
            s for s in tc_slots if s["start_time"] == time(9, 0) and s["day"] == 0
        ]
        self.assertEqual(
            len(mon_9_slots),
            1,
            "Same time on same day in two stages must yield exactly one TC slot",
        )

    def test_different_days_not_deduplicated(self):
        """The same start time on different days must produce separate TC slots."""
        slots = [
            make_slot(day_offset=0, hour=9, stage="primary"),  # Monday
            make_slot(day_offset=1, hour=9, stage="primary"),  # Tuesday
        ]
        tc_slots = _build_unique_tc_slots(slots)
        self.assertEqual(
            len(tc_slots),
            2,
            "Same time on different days must produce two distinct TC slots",
        )

    def test_empty_slots_returns_empty(self):
        """Empty weekly_slots must produce an empty TC slot list."""
        self.assertEqual(_build_unique_tc_slots([]), [])

    def test_only_recess_slots_returns_empty(self):
        """All-recess input must produce an empty TC slot list."""
        slots = [make_slot(day_offset=0, hour=11, duration_minutes=30, is_recess=True)]
        self.assertEqual(
            _build_unique_tc_slots(slots),
            [],
            "Only-recess input must produce empty TC slot list",
        )


class OverlapsAnyTest(SimpleTestCase):
    """EP: overlapping, adjacent, different-day intervals.  BVA at exact boundary."""

    def test_no_overlap_adjacent_intervals(self):
        """[09:00-10:00] and interval [10:00-11:00] must NOT overlap (strict)."""
        intervals = [(0, time(9, 0), time(10, 0))]
        self.assertFalse(
            _overlaps_any(0, time(10, 0), time(11, 0), intervals),
            "Adjacent intervals (share only boundary) must not overlap",
        )

    def test_strict_overlap_detected(self):
        """[09:00-10:30] and [10:00-11:00] share 30 minutes — must overlap."""
        intervals = [(0, time(9, 0), time(10, 30))]
        self.assertTrue(
            _overlaps_any(0, time(10, 0), time(11, 0), intervals),
            "Partially overlapping intervals must be detected",
        )

    def test_contained_interval_overlaps(self):
        """[09:00-12:00] fully contains [10:00-11:00] — must overlap."""
        intervals = [(0, time(9, 0), time(12, 0))]
        self.assertTrue(_overlaps_any(0, time(10, 0), time(11, 0), intervals))

    def test_different_day_no_overlap(self):
        """Same time on a different weekday must NOT overlap."""
        intervals = [(0, time(9, 0), time(10, 0))]  # day 0
        self.assertFalse(
            _overlaps_any(1, time(9, 0), time(10, 0), intervals),
            "Overlap check must be day-specific",
        )

    def test_empty_intervals_no_overlap(self):
        """Empty interval list must never indicate an overlap."""
        self.assertFalse(_overlaps_any(0, time(9, 0), time(10, 0), []))


class IsDeadGapTest(SimpleTestCase):
    """BVA: boundary at exact class time (strict < comparison), both-sides required."""

    def test_detects_gap_when_class_before_and_after(self):
        """Teacher with classes at 09:00 and 11:00 creates a dead gap at 10:00."""
        class_slots = {(1, 0): [time(9, 0), time(11, 0)]}
        self.assertTrue(
            _is_dead_gap(
                teacher_id=1,
                day=0,
                start_time=time(10, 0),
                class_slots_by_teacher_day=class_slots,
            ),
            "Slot between two classes must be a dead gap",
        )

    def test_no_gap_when_only_class_before(self):
        """Teacher with only a class before the slot (none after) must NOT be a gap."""
        class_slots = {(1, 0): [time(9, 0)]}
        self.assertFalse(
            _is_dead_gap(
                teacher_id=1,
                day=0,
                start_time=time(10, 0),
                class_slots_by_teacher_day=class_slots,
            ),
            "No class after the slot means not a dead gap",
        )

    def test_no_gap_when_only_class_after(self):
        """Teacher with only a class after the slot (none before) must NOT be a gap."""
        class_slots = {(1, 0): [time(11, 0)]}
        self.assertFalse(
            _is_dead_gap(
                teacher_id=1,
                day=0,
                start_time=time(10, 0),
                class_slots_by_teacher_day=class_slots,
            ),
            "No class before the slot means not a dead gap",
        )

    def test_bva_start_time_exactly_at_class_time_not_a_gap(self):
        """BVA: start_time == first class time → no class STRICTLY before → not a gap.

        The comparison is strict (<), so a teacher with classes at exactly
        10:00 and 11:00 is not considered to have a gap at 10:00 itself.
        """
        class_slots = {(1, 0): [time(10, 0), time(11, 0)]}
        self.assertFalse(
            _is_dead_gap(
                teacher_id=1,
                day=0,
                start_time=time(10, 0),
                class_slots_by_teacher_day=class_slots,
            ),
            "start_time == first class time means no class strictly before → not a gap",
        )

    def test_no_classes_at_all_not_a_gap(self):
        """Teacher with no classes on the day must not be considered to have a gap."""
        self.assertFalse(
            _is_dead_gap(
                teacher_id=1,
                day=0,
                start_time=time(10, 0),
                class_slots_by_teacher_day={},
            ),
        )

    def test_different_teacher_not_affected(self):
        """Dead-gap check must be per-teacher; another teacher's classes must not affect."""
        class_slots = {(99, 0): [time(9, 0), time(11, 0)]}  # teacher 99, not teacher 1
        self.assertFalse(
            _is_dead_gap(
                teacher_id=1,
                day=0,
                start_time=time(10, 0),
                class_slots_by_teacher_day=class_slots,
            ),
        )


class ComputeExactHoursDeficitTest(SimpleTestCase):
    """EP: exact-hours teacher vs. non-exact teacher."""

    def test_non_exact_teacher_always_zero_deficit(self):
        """A teacher with weekly_hours_exact=False must always have zero deficit."""
        teacher = make_teacher_stub(id=1, max_weekly_hours=10, weekly_hours_exact=False)
        deficit = _compute_exact_hours_deficit(
            teacher=teacher,
            schedule_minutes={1: 300},
            tc_minutes_assigned={},
        )
        self.assertEqual(deficit, 0, "Non-exact teacher must always have zero deficit")

    def test_exact_teacher_deficit_when_under_target(self):
        """Exact-hours teacher with 300 of 600 target minutes must show 300 deficit."""
        teacher = make_teacher_stub(
            id=1, max_weekly_hours=10, max_weekly_minutes=0, weekly_hours_exact=True
        )
        deficit = _compute_exact_hours_deficit(
            teacher=teacher,
            schedule_minutes={1: 300},  # 5h of 10h
            tc_minutes_assigned={},
        )
        self.assertEqual(
            deficit,
            300,
            "Exact teacher 5h short of 10h target must have 300-min deficit",
        )

    def test_exact_teacher_no_deficit_at_target(self):
        """Exact-hours teacher at exactly target minutes must have zero deficit."""
        teacher = make_teacher_stub(
            id=1, max_weekly_hours=10, max_weekly_minutes=0, weekly_hours_exact=True
        )
        deficit = _compute_exact_hours_deficit(
            teacher=teacher,
            schedule_minutes={1: 600},  # exactly 10h
            tc_minutes_assigned={},
        )
        self.assertEqual(deficit, 0, "Exact teacher at target must have zero deficit")

    def test_exact_teacher_over_target_returns_zero(self):
        """Exact-hours teacher over target must clamp to zero (not negative)."""
        teacher = make_teacher_stub(
            id=1, max_weekly_hours=10, max_weekly_minutes=0, weekly_hours_exact=True
        )
        deficit = _compute_exact_hours_deficit(
            teacher=teacher,
            schedule_minutes={1: 700},  # over target
            tc_minutes_assigned={},
        )
        self.assertEqual(deficit, 0, "Deficit must be clamped to zero when over target")

    def test_tc_minutes_counted_toward_target(self):
        """TC minutes already assigned must reduce the remaining deficit."""
        teacher = make_teacher_stub(
            id=1, max_weekly_hours=10, max_weekly_minutes=0, weekly_hours_exact=True
        )
        deficit = _compute_exact_hours_deficit(
            teacher=teacher,
            schedule_minutes={1: 300},
            tc_minutes_assigned={1: 300},  # together = 600 = target
        )
        self.assertEqual(
            deficit, 0, "TC minutes must count toward target when computing deficit"
        )
