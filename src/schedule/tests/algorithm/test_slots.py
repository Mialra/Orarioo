"""Tests for schedule.algorithm.slots slot-building utilities.

Covers: build_windows_from_stage_config (breaks, legacy keys, multiple breaks),
        slot_overlaps (adjacent, identical, partial), build_real_time_intervals.
Patterns: EP (valid config classes), BVA (break boundary times), AAA.
No database access.
"""

from datetime import time

from django.test import SimpleTestCase

from schedule.algorithm.slots import (build_real_time_intervals,
                                      build_windows_from_stage_config,
                                      slot_overlaps)
from schedule.tests.algorithm.factories import make_slot, make_week_slots


class BuildWindowsFromStageConfigTest(SimpleTestCase):
    """EP and BVA for break boundary correctness."""

    def _cfg(
        self,
        *,
        start="09:00",
        end="14:00",
        session_duration=60,
        breaks=None,
        break_start=None,
        break_end=None,
    ):
        cfg = {
            "start_time": start,
            "end_time": end,
            "session_duration": session_duration,
        }
        if breaks is not None:
            cfg["breaks"] = breaks
        if break_start:
            cfg["break_start"] = break_start
        if break_end:
            cfg["break_end"] = break_end
        return cfg

    # --- correct slot count ---

    def test_no_break_fills_entire_day(self):
        """09:00-14:00 with no break must produce 5 teaching slots and 0 recess."""
        windows = build_windows_from_stage_config(self._cfg(start="09:00", end="14:00"))
        teaching = [w for w in windows if not w[2]]
        recess = [w for w in windows if w[2]]
        self.assertEqual(
            len(teaching), 5, "5 one-hour slots for 09:00-14:00 with no break"
        )
        self.assertEqual(len(recess), 0)

    def test_single_break_produces_correct_counts(self):
        """08:00-14:30 with one break at 11:00-11:30 → 6 teaching slots + 1 recess."""
        windows = build_windows_from_stage_config(
            self._cfg(
                start="08:00", end="14:30", breaks=[{"start": "11:00", "end": "11:30"}]
            )
        )
        teaching = [w for w in windows if not w[2]]
        recess = [w for w in windows if w[2]]
        self.assertEqual(
            len(teaching),
            6,
            "08:00-14:30 with 11:00-11:30 break must produce 6 teaching slots",
        )
        self.assertEqual(len(recess), 1)

    def test_two_breaks_produce_two_recess_slots(self):
        """Two breaks in a day must produce exactly 2 recess slots."""
        windows = build_windows_from_stage_config(
            self._cfg(
                start="08:00",
                end="15:00",
                breaks=[
                    {"start": "10:00", "end": "10:30"},
                    {"start": "12:30", "end": "13:00"},
                ],
            )
        )
        recess = [w for w in windows if w[2]]
        self.assertEqual(
            len(recess), 2, "Two breaks must produce exactly 2 recess slots"
        )

    # --- break boundary correctness ---

    def test_no_slot_spans_break_boundary(self):
        """No teaching slot must start before and end after a break boundary."""
        windows = build_windows_from_stage_config(
            self._cfg(breaks=[{"start": "11:30", "end": "12:00"}])
        )
        break_start = time(11, 30)
        break_end = time(12, 0)
        for start_t, end_t, is_recess in windows:
            if is_recess:
                continue
            self.assertFalse(
                start_t < break_start < end_t,
                f"Teaching slot {start_t}-{end_t} must not span break boundary at 11:30",
            )
            self.assertFalse(
                start_t < break_end < end_t,
                f"Teaching slot {start_t}-{end_t} must not span break end at 12:00",
            )

    def test_slot_ends_exactly_at_break_start(self):
        """The last teaching slot before a break must end exactly at break_start."""
        windows = build_windows_from_stage_config(
            self._cfg(breaks=[{"start": "11:30", "end": "12:00"}])
        )
        teaching_ends = [w[1] for w in windows if not w[2]]
        self.assertIn(
            time(11, 30),
            teaching_ends,
            "A teaching slot must end exactly at 11:30 (the break start)",
        )

    def test_slot_starts_exactly_at_break_end(self):
        """The first teaching slot after a break must start exactly at break_end."""
        windows = build_windows_from_stage_config(
            self._cfg(breaks=[{"start": "11:30", "end": "12:00"}])
        )
        teaching_starts = [w[0] for w in windows if not w[2]]
        self.assertIn(
            time(12, 0),
            teaching_starts,
            "A teaching slot must start exactly at 12:00 (the break end)",
        )

    # --- legacy break_start / break_end keys ---

    def test_legacy_break_keys_match_new_format(self):
        """break_start/break_end keys must produce identical output to breaks list format."""
        cfg_new = self._cfg(breaks=[{"start": "11:30", "end": "12:00"}])
        cfg_legacy = self._cfg(break_start="11:30", break_end="12:00")
        self.assertEqual(
            build_windows_from_stage_config(cfg_new),
            build_windows_from_stage_config(cfg_legacy),
            "Legacy single-break keys must be equivalent to new breaks list format",
        )

    # --- recess tuple shape ---

    def test_recess_tuple_is_marked(self):
        """Every recess window must have is_recess=True as its third element."""
        windows = build_windows_from_stage_config(
            self._cfg(breaks=[{"start": "11:00", "end": "11:30"}])
        )
        for start_t, end_t, is_recess in windows:
            if start_t == time(11, 0) and end_t == time(11, 30):
                self.assertTrue(is_recess, "The break window must have is_recess=True")


class SlotOverlapsTest(SimpleTestCase):
    """EP: no overlap (adjacent), identical, partial overlap.
    BVA: exact boundary sharing.
    """

    def test_adjacent_slots_do_not_overlap(self):
        """[09:00-10:00] and [10:00-11:00] share only a boundary → strict overlap = False."""
        s1 = make_slot(hour=9)
        s2 = make_slot(hour=10)
        self.assertFalse(
            slot_overlaps(left_slot=s1, right_slot=s2),
            "Adjacent slots sharing only a boundary must NOT overlap (strict)",
        )

    def test_identical_slots_overlap(self):
        """Two identical slots must overlap."""
        s = make_slot(hour=9)
        self.assertTrue(
            slot_overlaps(left_slot=s, right_slot=s),
            "Identical slots must overlap",
        )

    def test_partial_overlap_detected(self):
        """[09:00-10:30] and [10:00-11:00] share 30 minutes → overlap = True."""
        s1 = make_slot(hour=9, duration_minutes=90)
        s2 = make_slot(hour=10)
        self.assertTrue(
            slot_overlaps(left_slot=s1, right_slot=s2),
            "Partially overlapping slots must be detected",
        )

    def test_contained_slot_overlaps(self):
        """[09:00-12:00] fully contains [10:00-11:00] → overlap = True."""
        outer = make_slot(hour=9, duration_minutes=180)
        inner = make_slot(hour=10)
        self.assertTrue(slot_overlaps(left_slot=outer, right_slot=inner))

    def test_no_overlap_before(self):
        """[08:00-09:00] and [09:00-10:00] are adjacent → no overlap."""
        s1 = make_slot(hour=8)
        s2 = make_slot(hour=9)
        self.assertFalse(slot_overlaps(left_slot=s1, right_slot=s2))

    def test_different_days_do_not_overlap(self):
        """Same time on different days must not overlap."""
        s1 = make_slot(day_offset=0, hour=9)
        s2 = make_slot(day_offset=1, hour=9)
        self.assertFalse(
            slot_overlaps(left_slot=s1, right_slot=s2),
            "Same hour on different days must not overlap",
        )


class BuildRealTimeIntervalsTest(SimpleTestCase):
    """Structural tests for build_real_time_intervals output."""

    def test_returns_list(self):
        slots = make_week_slots()
        result = build_real_time_intervals(slots=slots)
        self.assertIsInstance(result, list)

    def test_every_interval_has_required_keys(self):
        """Each interval dict must contain day_idx, start, end, slot_indices."""
        slots = make_week_slots()
        intervals = build_real_time_intervals(slots=slots)
        for iv in intervals:
            for key in ("day_idx", "start", "end", "slot_indices"):
                self.assertIn(key, iv, f"Interval must contain key '{key}'")

    def test_every_slot_covered_by_at_least_one_interval(self):
        """Every slot index must appear in at least one interval's slot_indices list."""
        slots = make_week_slots(hours_per_day=[9, 10])
        intervals = build_real_time_intervals(slots=slots)
        all_covered = set()
        for iv in intervals:
            all_covered.update(iv["slot_indices"])
        for idx in range(len(slots)):
            self.assertIn(
                idx,
                all_covered,
                f"Slot {idx} must be covered by at least one real-time interval",
            )

    def test_empty_slots_returns_empty(self):
        self.assertEqual(build_real_time_intervals(slots=[]), [])

    def test_interval_start_before_end(self):
        """Each interval must have start strictly before end."""
        slots = make_week_slots()
        for iv in build_real_time_intervals(slots=slots):
            self.assertLess(
                iv["start"],
                iv["end"],
                "Each interval's start must be before its end",
            )
