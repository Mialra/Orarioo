"""Tests for schedule.algorithm.constraints.soft.evaluate_soft_score.

Covers: Equivalence Partitioning across all four score components (subject
preferences, teacher preferences, subject day spread, teacher gap penalty)
plus Boundary Value Analysis on weights and the flag-disabled paths.
No database access — all inputs are built from pure-dict factories.
"""

from django.test import SimpleTestCase

from schedule.algorithm.constraints.soft import (
    PREFER_NO_WEIGHT_PENALTY,
    PREFER_YES_WEIGHT,
    SUBJECT_DAY_SPREAD_WEIGHT,
    TEACHER_GAP_WEIGHT_PENALTY,
    TEACHER_PREFER_NO_WEIGHT_PENALTY,
    TEACHER_PREFER_YES_WEIGHT,
    evaluate_soft_score,
)
from schedule.tests.algorithm.factories import (
    make_session,
    make_subject_stub,
    make_teacher_stub,
    make_week_slots,
)
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState


class EvaluateSoftScoreSubjectPreferencesTest(SimpleTestCase):
    """EP: three classes for subject time preference state."""

    def _slots(self):
        return make_week_slots(hours_per_day=[9])  # 5 slots, one per day

    def test_prefer_yes_adds_weight(self):
        """PREFER_YES on the assigned slot must contribute +PREFER_YES_WEIGHT."""
        slots = self._slots()
        subject = make_subject_stub(
            id=1, time_preferences={"MON_09:00": SubjectTimePreferenceState.PREFER_YES}
        )
        sessions = [make_session(subject=subject, teacher_id=1)]
        result = evaluate_soft_score(
            slot_by_session=[0], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["subject_preferences"],
            PREFER_YES_WEIGHT,
            "PREFER_YES subject on assigned slot must add PREFER_YES_WEIGHT",
        )

    def test_prefer_no_subtracts_penalty(self):
        """PREFER_NO on the assigned slot must contribute -PREFER_NO_WEIGHT_PENALTY."""
        slots = self._slots()
        subject = make_subject_stub(
            id=1, time_preferences={"MON_09:00": SubjectTimePreferenceState.PREFER_NO}
        )
        sessions = [make_session(subject=subject, teacher_id=1)]
        result = evaluate_soft_score(
            slot_by_session=[0], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["subject_preferences"],
            -PREFER_NO_WEIGHT_PENALTY,
            "PREFER_NO subject on assigned slot must subtract PREFER_NO_WEIGHT_PENALTY",
        )

    def test_available_state_contributes_zero(self):
        """AVAILABLE (no preference key) must not change the subject score."""
        slots = self._slots()
        subject = make_subject_stub(id=1, time_preferences={})
        sessions = [make_session(subject=subject)]
        result = evaluate_soft_score(
            slot_by_session=[0], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["subject_preferences"],
            0,
            "No time preference must yield zero subject score",
        )

    def test_subject_preferences_disabled_key_absent(self):
        """Disabling subject preferences must remove the key from breakdown entirely."""
        slots = self._slots()
        subject = make_subject_stub(
            id=1, time_preferences={"MON_09:00": SubjectTimePreferenceState.PREFER_YES}
        )
        sessions = [make_session(subject=subject)]
        result = evaluate_soft_score(
            slot_by_session=[0],
            sessions=sessions,
            slots=slots,
            generation_options={"enable_subject_time_preferences": False},
        )
        self.assertNotIn(
            "subject_preferences",
            result["breakdown"],
            "Disabled subject preferences must be absent from breakdown",
        )


class EvaluateSoftScoreTeacherPreferencesTest(SimpleTestCase):
    """EP: three classes for teacher time preference state."""

    def _slots(self):
        return make_week_slots(hours_per_day=[9])

    def test_prefer_yes_adds_weight(self):
        """PREFER_YES on the teacher's assigned slot must contribute +TEACHER_PREFER_YES_WEIGHT."""
        slots = self._slots()
        teacher = make_teacher_stub(
            id=2,
            time_preferences={"MON_09:00": TeacherTimePreferenceState.PREFER_YES},
        )
        sessions = [make_session(teacher=teacher)]
        result = evaluate_soft_score(
            slot_by_session=[0], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["teacher_preferences"],
            TEACHER_PREFER_YES_WEIGHT,
            "PREFER_YES teacher must add TEACHER_PREFER_YES_WEIGHT",
        )

    def test_prefer_no_subtracts_penalty(self):
        """PREFER_NO on the teacher's assigned slot must subtract the penalty."""
        slots = self._slots()
        teacher = make_teacher_stub(
            id=2,
            time_preferences={"MON_09:00": TeacherTimePreferenceState.PREFER_NO},
        )
        sessions = [make_session(teacher=teacher)]
        result = evaluate_soft_score(
            slot_by_session=[0], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["teacher_preferences"],
            -TEACHER_PREFER_NO_WEIGHT_PENALTY,
            "PREFER_NO teacher must subtract TEACHER_PREFER_NO_WEIGHT_PENALTY",
        )

    def test_teacher_preferences_disabled_key_absent(self):
        """Disabling teacher preferences must remove key from breakdown."""
        slots = self._slots()
        teacher = make_teacher_stub(
            id=2,
            time_preferences={"MON_09:00": TeacherTimePreferenceState.PREFER_YES},
        )
        sessions = [make_session(teacher=teacher)]
        result = evaluate_soft_score(
            slot_by_session=[0],
            sessions=sessions,
            slots=slots,
            generation_options={"enable_teacher_time_preferences": False},
        )
        self.assertNotIn(
            "teacher_preferences",
            result["breakdown"],
            "Disabled teacher preferences must be absent from breakdown",
        )


class EvaluateSoftScoreSubjectDaySpreadTest(SimpleTestCase):
    """EP: single-session subject (no bonus), two sessions same day, two sessions different days."""

    def test_single_session_no_spread_bonus(self):
        """A subject with only one session cannot spread; must earn 0 spread bonus."""
        slots = make_week_slots(hours_per_day=[9])
        subject = make_subject_stub(id=5)
        sessions = [make_session(subject=subject)]
        result = evaluate_soft_score(
            slot_by_session=[0], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["subject_spread"],
            0,
            "Single session subject must earn zero spread bonus",
        )

    def test_two_sessions_same_day_spread_one_day(self):
        """Two sessions of same subject on same day cover exactly 1 day → 1× WEIGHT."""
        # day 0 has slots at index 0 (09:00) and 1 (10:00)
        slots = make_week_slots(hours_per_day=[9, 10])
        subject = make_subject_stub(id=5)
        sessions = [make_session(subject=subject), make_session(subject=subject)]
        result = evaluate_soft_score(
            slot_by_session=[0, 1], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["subject_spread"],
            SUBJECT_DAY_SPREAD_WEIGHT * 1,
            "Two sessions same day must earn spread for 1 day only",
        )

    def test_two_sessions_different_days_spread_two_days(self):
        """Two sessions on different days cover 2 days → 2× WEIGHT."""
        # make_week_slots with 1 hour/day → slot 0 = MON, slot 1 = TUE
        slots = make_week_slots(hours_per_day=[9])
        subject = make_subject_stub(id=5)
        sessions = [make_session(subject=subject), make_session(subject=subject)]
        result = evaluate_soft_score(
            slot_by_session=[0, 1], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["subject_spread"],
            SUBJECT_DAY_SPREAD_WEIGHT * 2,
            "Two sessions on different days must earn spread for 2 days",
        )

    def test_subject_spread_disabled_key_absent(self):
        """Disabling spread must remove the key from breakdown."""
        slots = make_week_slots(hours_per_day=[9])
        subject = make_subject_stub(id=5)
        sessions = [make_session(subject=subject), make_session(subject=subject)]
        result = evaluate_soft_score(
            slot_by_session=[0, 1],
            sessions=sessions,
            slots=slots,
            generation_options={"enable_subject_day_spread": False},
        )
        self.assertNotIn(
            "subject_spread",
            result["breakdown"],
            "Disabled spread must be absent from breakdown",
        )


class EvaluateSoftScoreTeacherGapTest(SimpleTestCase):
    """EP: no gap, one gap, gap disabled.
    BVA: slots 0 & 2 same day (gap at 1), slots 0 & 1 (no gap).
    """

    def _three_slot_day(self):
        """Return 15 slots: 3 per day (09:00, 10:00, 11:00) over 5 days."""
        return make_week_slots(hours_per_day=[9, 10, 11])

    def test_no_gap_consecutive_slots_zero_penalty(self):
        """Consecutive slots (0, 1) for same teacher must yield zero gap penalty."""
        slots = self._three_slot_day()
        teacher = make_teacher_stub(id=7)
        sessions = [make_session(teacher=teacher), make_session(teacher=teacher)]
        result = evaluate_soft_score(
            slot_by_session=[0, 1], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["teacher_gaps"],
            0,
            "Consecutive slots must not incur gap penalty",
        )

    def test_gap_between_slots_incurs_penalty(self):
        """Slots 0 (09:00) and 2 (11:00) same day with slot 1 (10:00) unassigned → 1 gap."""
        slots = self._three_slot_day()
        teacher = make_teacher_stub(id=7)
        sessions = [make_session(teacher=teacher), make_session(teacher=teacher)]
        result = evaluate_soft_score(
            slot_by_session=[0, 2], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["teacher_gaps"],
            -TEACHER_GAP_WEIGHT_PENALTY,
            "One inner gap must cost exactly TEACHER_GAP_WEIGHT_PENALTY",
        )

    def test_gap_minimization_disabled_key_absent(self):
        """Disabling gap minimization must remove key from breakdown even with a gap."""
        slots = self._three_slot_day()
        teacher = make_teacher_stub(id=7)
        sessions = [make_session(teacher=teacher), make_session(teacher=teacher)]
        result = evaluate_soft_score(
            slot_by_session=[0, 2],
            sessions=sessions,
            slots=slots,
            generation_options={"enable_teacher_gap_minimization": False},
        )
        self.assertNotIn(
            "teacher_gaps",
            result["breakdown"],
            "Disabled gap minimization must be absent from breakdown",
        )

    def test_different_teachers_independent_gaps(self):
        """Two teachers each with a gap must each incur the penalty (total = -16)."""
        slots = self._three_slot_day()
        t1 = make_teacher_stub(id=1)
        t2 = make_teacher_stub(id=2)
        sessions = [
            make_session(teacher=t1),
            make_session(teacher=t1),
            make_session(teacher=t2),
            make_session(teacher=t2),
        ]
        result = evaluate_soft_score(
            slot_by_session=[0, 2, 0, 2], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["breakdown"]["teacher_gaps"],
            -TEACHER_GAP_WEIGHT_PENALTY * 2,
            "Two teachers each with a gap must incur penalty twice",
        )


class EvaluateSoftScoreInvariantTest(SimpleTestCase):
    """Structural invariant: total must always equal sum of breakdown values."""

    def test_total_equals_sum_of_breakdown(self):
        """total field must equal sum(breakdown.values()) for any non-trivial input."""
        slots = make_week_slots(hours_per_day=[9, 10, 11])
        subject = make_subject_stub(
            id=1,
            time_preferences={"MON_09:00": SubjectTimePreferenceState.PREFER_YES},
        )
        teacher = make_teacher_stub(
            id=1,
            time_preferences={"MON_10:00": TeacherTimePreferenceState.PREFER_NO},
        )
        sessions = [make_session(subject=subject, teacher=teacher)]
        result = evaluate_soft_score(
            slot_by_session=[0], sessions=sessions, slots=slots
        )
        self.assertEqual(
            result["total"],
            sum(result["breakdown"].values()),
            "total must always equal sum of all breakdown component values",
        )

    def test_empty_sessions_zero_score(self):
        """Zero sessions must produce a zero total with empty breakdown values."""
        slots = make_week_slots(hours_per_day=[9])
        result = evaluate_soft_score(slot_by_session=[], sessions=[], slots=slots)
        self.assertEqual(result["total"], 0, "Empty sessions must produce total of 0")
        for key, val in result["breakdown"].items():
            self.assertEqual(val, 0, f"breakdown[{key!r}] must be 0 for empty sessions")
