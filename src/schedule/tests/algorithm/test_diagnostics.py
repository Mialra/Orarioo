"""Tests for schedule.algorithm.diagnostics.

Covers: build_diagnostic, sort_diagnostics, collect_generation_diagnostics.
Critical invariant tested: CAPACITY diagnostics must have rank < BOTTLENECK_RANK
so the pipeline aborts before calling the expensive solver.
Patterns: EP (diagnostic hierarchy classes), BVA (rank ordering), AAA.
No database access.
"""

from django.test import SimpleTestCase

from schedule.algorithm.diagnostics import (BOTTLENECK_RANK, CAPACITY_RANK,
                                            CONFIGURATION_RANK, FALLBACK_RANK,
                                            build_diagnostic,
                                            collect_generation_diagnostics,
                                            sort_diagnostics)
from schedule.tests.algorithm.factories import (make_group_stub, make_session,
                                                make_teacher_stub,
                                                make_week_slots)


class BuildDiagnosticTest(SimpleTestCase):
    """EP: required keys present, optional keys absent/present based on args."""

    def test_required_keys_always_present(self):
        """Every diagnostic must contain code, message, context, severity, scope, rank."""
        d = build_diagnostic("TEST_CODE", "test message")
        for key in ("code", "message", "context", "severity", "scope", "rank"):
            self.assertIn(key, d, f"Diagnostic must contain key '{key}'")

    def test_rank_defaults_to_fallback(self):
        """When rank is not provided it must default to FALLBACK_RANK."""
        d = build_diagnostic("X", "y")
        self.assertEqual(d["rank"], FALLBACK_RANK, "Default rank must be FALLBACK_RANK")

    def test_explicit_rank_stored(self):
        """An explicit rank argument must be stored verbatim."""
        d = build_diagnostic("X", "y", rank=CONFIGURATION_RANK)
        self.assertEqual(d["rank"], CONFIGURATION_RANK)

    def test_suggestions_absent_when_not_provided(self):
        """suggestions key must be absent when no suggestions are given."""
        d = build_diagnostic("X", "y")
        self.assertNotIn(
            "suggestions", d, "suggestions must not appear unless provided"
        )

    def test_suggestions_present_when_provided(self):
        """suggestions list must be stored when provided."""
        d = build_diagnostic("X", "y", suggestions=["do something"])
        self.assertIn("suggestions", d)
        self.assertEqual(d["suggestions"], ["do something"])

    def test_context_defaults_to_empty_dict(self):
        """context must default to an empty dict, never None."""
        d = build_diagnostic("X", "y")
        self.assertEqual(d["context"], {})


class SortDiagnosticsTest(SimpleTestCase):
    """BVA: ranking hierarchy CONFIGURATION < CAPACITY < AVAILABILITY < BOTTLENECK < FALLBACK."""

    def test_lower_rank_appears_first(self):
        """sort_diagnostics must return diagnostics ordered by ascending rank."""
        diags = [
            build_diagnostic("B", "b", rank=BOTTLENECK_RANK),
            build_diagnostic("C", "c", rank=CONFIGURATION_RANK),
            build_diagnostic("CAP", "cap", rank=CAPACITY_RANK),
        ]
        sorted_diags = sort_diagnostics(diags)
        ranks = [d["rank"] for d in sorted_diags]
        self.assertEqual(
            ranks,
            sorted(ranks),
            "sort_diagnostics must order by ascending rank",
        )

    def test_same_rank_stable_by_code(self):
        """Diagnostics with the same rank must be sorted lexicographically by code."""
        diags = [
            build_diagnostic("Z_CODE", "z", rank=10),
            build_diagnostic("A_CODE", "a", rank=10),
        ]
        sorted_diags = sort_diagnostics(diags)
        self.assertEqual(sorted_diags[0]["code"], "A_CODE")

    def test_empty_list_returns_empty(self):
        """sort_diagnostics([]) must return []."""
        self.assertEqual(sort_diagnostics([]), [])

    def test_none_returns_empty(self):
        """sort_diagnostics(None) must return []."""
        self.assertEqual(sort_diagnostics(None), [])


class CollectDiagnostics_ConfigurationTest(SimpleTestCase):
    """EP: configuration-level problems detected before solver runs."""

    def test_no_teachers_produces_missing_teachers_code(self):
        """Passing teachers=[] must produce a MISSING_TEACHERS diagnostic."""
        diags = collect_generation_diagnostics(
            sessions=[],
            slots=[],
            classrooms=[],
            subjects=[],
            teachers=[],
        )
        codes = [d["code"] for d in diags]
        self.assertIn(
            "MISSING_TEACHERS",
            codes,
            "Empty teacher list must produce MISSING_TEACHERS diagnostic",
        )

    def test_missing_teachers_has_configuration_rank(self):
        """MISSING_TEACHERS must have CONFIGURATION_RANK so it blocks the solver."""
        diags = collect_generation_diagnostics(
            sessions=[], slots=[], classrooms=[], subjects=[], teachers=[]
        )
        missing = [d for d in diags if d["code"] == "MISSING_TEACHERS"]
        self.assertTrue(missing, "MISSING_TEACHERS diagnostic must be present")
        self.assertEqual(
            missing[0]["rank"],
            CONFIGURATION_RANK,
            "MISSING_TEACHERS must have CONFIGURATION_RANK",
        )

    def test_no_subjects_produces_missing_subjects_code(self):
        """Passing subjects=[] with a teacher must produce a MISSING_SUBJECTS diagnostic."""
        teacher = make_teacher_stub(id=1)
        diags = collect_generation_diagnostics(
            sessions=[],
            slots=[],
            classrooms=[],
            subjects=[],
            teachers=[teacher],
        )
        codes = [d["code"] for d in diags]
        self.assertIn(
            "MISSING_SUBJECTS",
            codes,
            "Empty subject list must produce MISSING_SUBJECTS diagnostic",
        )


class CollectDiagnostics_CapacityRankTest(SimpleTestCase):
    """Critical: capacity diagnostics must have rank < BOTTLENECK_RANK.

    The generation pipeline checks `rank < BOTTLENECK_RANK` to decide whether
    to abort before calling the solver.  If a capacity violation has rank >=
    BOTTLENECK_RANK it is silently ignored and the solver wastes minutes on an
    infeasible problem.
    """

    def _sessions_over_primary_limit(self, count=26):
        """Return `count` sessions all assigned to the same PRIMARY group."""
        group = make_group_stub(id=1, stage="primary")
        teacher = make_teacher_stub(id=1, max_weekly_hours=30)
        return [make_session(group=group, teacher=teacher) for _ in range(count)]

    def _big_slots(self):
        return make_week_slots(hours_per_day=[8, 9, 10, 11, 12, 13, 14])

    def test_group_over_weekly_limit_produces_capacity_diagnostic(self):
        """26 sessions for a PRIMARY group must produce a capacity-related diagnostic."""
        sessions = self._sessions_over_primary_limit(26)
        slots = self._big_slots()
        diags = collect_generation_diagnostics(
            sessions=sessions, slots=slots, classrooms=[]
        )
        capacity_codes = [d["code"] for d in diags if d["rank"] <= CAPACITY_RANK]
        self.assertTrue(
            capacity_codes,
            "26 sessions for PRIMARY group must produce at least one capacity diagnostic",
        )

    def test_capacity_diagnostic_rank_is_below_bottleneck(self):
        """The capacity diagnostic rank must be < BOTTLENECK_RANK to block the solver."""
        sessions = self._sessions_over_primary_limit(26)
        slots = self._big_slots()
        diags = collect_generation_diagnostics(
            sessions=sessions, slots=slots, classrooms=[]
        )
        blocking = [d for d in diags if d["rank"] < BOTTLENECK_RANK]
        self.assertTrue(
            blocking,
            "At least one blocking diagnostic (rank < BOTTLENECK_RANK) must be present "
            "when a group exceeds its weekly limit",
        )

    def test_first_sorted_diagnostic_is_most_actionable(self):
        """After sorting, the first diagnostic must be the lowest rank."""
        sessions = self._sessions_over_primary_limit(26)
        slots = self._big_slots()
        diags = collect_generation_diagnostics(
            sessions=sessions, slots=slots, classrooms=[]
        )
        if len(diags) >= 2:
            self.assertLessEqual(
                diags[0]["rank"],
                diags[1]["rank"],
                "Diagnostics must be sorted ascending by rank after collection",
            )
