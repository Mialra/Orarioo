"""Tests for schedule.algorithm.evaluator.ScheduleEvaluator.

Covers: get_expected_hours_for_stage (all stages + unknown fallback),
        _detect_internal_gaps (gap detected, break hour skipped, no gap).
Patterns: EP (stage classes), BVA (break boundary hours), AAA.
No database access — all inputs are plain dicts and SimpleNamespace stubs.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from schedule.algorithm.evaluator import ScheduleEvaluator


def _make_group_stub(*, id=1, name="1A"):
    return SimpleNamespace(id=id, name=name)


def _make_day_data(*, group=None, stage="primary"):
    """Return a minimal day_data dict for _detect_internal_gaps."""
    g = group or _make_group_stub()
    return {
        "group": g,
        "group_name": g.name,
        "date": "2024-01-08",
        "hours": set(),
        "stage": stage,
    }


class GetExpectedHoursForStageTest(SimpleTestCase):
    """EP: three stage classes + unknown-stage fallback.
    BVA: break boundary integers for each stage.
    """

    def test_preschool_expected_hours(self):
        """Preschool break is (10.5, 11) — no integer falls in [10.5, 11) so all 9-13 included."""
        # Actually break = (10.5, 11): 10.5 <= h < 11 → no integer satisfies this
        # So expected = {9, 10, 11, 12, 13}? Wait, let me re-check STAGE_HOURS:
        # preschool: start=9, end=13, break=(10.5, 11)
        # for h in range(9, 14): skip if 10.5 <= h < 11 → no integer in [10.5, 11)
        # So all 5 hours present
        expected = ScheduleEvaluator.get_expected_hours_for_stage("preschool")
        self.assertIn(9, expected, "Hour 9 must be expected for preschool")
        self.assertIn(10, expected, "Hour 10 must be expected for preschool")
        self.assertIn(11, expected, "Hour 11 must be expected for preschool")
        self.assertIn(13, expected, "Hour 13 must be expected for preschool")
        self.assertNotIn(8, expected, "Hour 8 must not be expected for preschool")

    def test_primary_expected_hours(self):
        """Primary break is (11.5, 12) — no integer falls in [11.5, 12), so hours 9-13 all present."""
        expected = ScheduleEvaluator.get_expected_hours_for_stage("primary")
        self.assertIn(9, expected)
        self.assertIn(10, expected)
        self.assertIn(11, expected)
        self.assertIn(12, expected)
        self.assertIn(13, expected)
        self.assertNotIn(8, expected, "Hour 8 must not be expected for primary")

    def test_secondary_break_excludes_hour_11(self):
        """Secondary break is (11, 11.5) — integer 11 satisfies 11 <= 11 < 11.5 → excluded."""
        expected = ScheduleEvaluator.get_expected_hours_for_stage("secondary")
        self.assertNotIn(
            11,
            expected,
            "Hour 11 must be excluded for secondary (break starts at 11:00)",
        )
        self.assertIn(
            8, expected, "Hour 8 must be included for secondary (starts at 8:00)"
        )
        self.assertIn(
            12, expected, "Hour 12 must be included for secondary (after break)"
        )
        self.assertIn(13, expected, "Hour 13 must be included for secondary")

    def test_unknown_stage_falls_back_to_primary(self):
        """An unrecognised stage name must fall back to primary hours."""
        unknown = ScheduleEvaluator.get_expected_hours_for_stage("nonexistent_stage")
        primary = ScheduleEvaluator.get_expected_hours_for_stage("primary")
        self.assertEqual(
            unknown,
            primary,
            "Unknown stage must fall back to primary expected hours",
        )

    def test_returns_set_type(self):
        """Return value must be a set so 'in' membership checks are O(1)."""
        result = ScheduleEvaluator.get_expected_hours_for_stage("primary")
        self.assertIsInstance(
            result, set, "get_expected_hours_for_stage must return a set"
        )


class DetectInternalGapsTest(SimpleTestCase):
    """EP: no gap, one gap, gap at break hour (suppressed).
    BVA: gap exactly one slot apart vs. two slots apart.
    """

    def _primary_expected(self):
        return ScheduleEvaluator.get_expected_hours_for_stage("primary")

    def _secondary_expected(self):
        return ScheduleEvaluator.get_expected_hours_for_stage("secondary")

    def test_consecutive_hours_no_gap(self):
        """Classes at [9, 10, 11] with no missing expected hour must yield zero defects."""
        day_data = _make_day_data(stage="primary")
        defects = ScheduleEvaluator._detect_internal_gaps(
            day_data, hours_list=[9, 10, 11], expected_hours=self._primary_expected()
        )
        self.assertEqual(
            defects, [], "No gap between consecutive hours must produce no defects"
        )

    def test_single_session_no_gap(self):
        """A single session has nothing to compare against — must yield zero defects."""
        day_data = _make_day_data(stage="primary")
        defects = ScheduleEvaluator._detect_internal_gaps(
            day_data, hours_list=[9], expected_hours=self._primary_expected()
        )
        self.assertEqual(defects, [])

    def test_gap_between_9_and_11_detects_hour_10(self):
        """Classes at [9, 11] with hour 10 in expected_hours must produce one INTERNAL defect."""
        day_data = _make_day_data(stage="primary")
        defects = ScheduleEvaluator._detect_internal_gaps(
            day_data, hours_list=[9, 11], expected_hours=self._primary_expected()
        )
        self.assertEqual(
            len(defects), 1, "One missing expected hour must produce exactly one defect"
        )
        self.assertEqual(defects[0]["gap_type"], "INTERNAL")
        self.assertEqual(
            defects[0]["context"]["hour"],
            10,
            "Detected gap must be at hour 10",
        )

    def test_gap_between_9_and_13_detects_multiple_hours(self):
        """Classes at [9, 13] with hours 10, 11, 12 in expected_hours → 3 defects."""
        day_data = _make_day_data(stage="primary")
        # primary expected = {9,10,11,12,13}; missing between 9 and 13 = 10,11,12
        defects = ScheduleEvaluator._detect_internal_gaps(
            day_data, hours_list=[9, 13], expected_hours=self._primary_expected()
        )
        self.assertEqual(
            len(defects),
            3,
            "Three missing expected hours between 9 and 13 must produce 3 defects",
        )

    def test_gap_at_break_hour_not_flagged_secondary(self):
        """Secondary break is at hour 11 (excluded from expected_hours).
        Classes at [10, 12] with hour 11 missing must NOT produce a defect because
        hour 11 is not in secondary expected_hours.
        """
        day_data = _make_day_data(stage="secondary")
        secondary_expected = self._secondary_expected()
        # Confirm hour 11 is indeed excluded from secondary expected hours
        self.assertNotIn(11, secondary_expected)

        defects = ScheduleEvaluator._detect_internal_gaps(
            day_data,
            hours_list=[10, 12],
            expected_hours=secondary_expected,
        )
        self.assertEqual(
            defects,
            [],
            "Missing hour 11 (break) for secondary must not be flagged as a gap",
        )

    def test_defect_contains_required_fields(self):
        """Each defect dict must contain entity_id, entity_name, gap_type, severity."""
        day_data = _make_day_data(stage="primary")
        defects = ScheduleEvaluator._detect_internal_gaps(
            day_data, hours_list=[9, 11], expected_hours=self._primary_expected()
        )
        defect = defects[0]
        for field in (
            "entity_id",
            "entity_name",
            "entity_type",
            "severity",
            "gap_type",
        ):
            self.assertIn(field, defect, f"Defect dict must contain field '{field}'")
        self.assertEqual(defect["entity_type"], "group")
        self.assertEqual(defect["gap_type"], "INTERNAL")
