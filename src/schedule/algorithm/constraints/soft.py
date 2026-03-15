from schedule.algorithm.constraints.hard import session_preference_state
from schedule.algorithm.slots import build_slot_preference_index
from subject.models import SubjectTimePreferenceState


TC_SLOT_COVERAGE_WEIGHT = 5
PREFER_YES_WEIGHT = 2
PREFER_NO_WEIGHT = -2


def apply_soft_constraints(*, model, x, sessions, slots):
    """Apply optional optimization goals without breaking hard constraints."""
    objective_terms = []
    objective_terms.extend(
        _tc_slot_coverage_terms(model=model, x=x, sessions=sessions, slots=slots)
    )
    objective_terms.extend(
        _subject_time_preference_terms(x=x, sessions=sessions, slots=slots)
    )

    if objective_terms:
        model.Maximize(sum(objective_terms))


def _tc_slot_coverage_terms(*, model, x, sessions, slots):
    """
    Spread TC sessions across as many weekly slots as possible.

    This increases the chance of having at least one teacher in guard duty
    (TC) available in more moments of the timetable whenever feasible.
    """
    tc_session_indices = _tc_session_indices(sessions=sessions)
    if not tc_session_indices:
        return []

    weighted_terms = []
    for p_idx in range(len(slots)):
        has_tc_in_slot = model.NewBoolVar(f"tc_covered_p{p_idx}")
        tc_in_slot_expr = sum(x[(s_idx, p_idx)] for s_idx in tc_session_indices)

        model.Add(tc_in_slot_expr >= 1).OnlyEnforceIf(has_tc_in_slot)
        model.Add(tc_in_slot_expr == 0).OnlyEnforceIf(has_tc_in_slot.Not())

        weighted_terms.append(TC_SLOT_COVERAGE_WEIGHT * has_tc_in_slot)

    return weighted_terms


def _subject_time_preference_terms(*, x, sessions, slots):
    slot_preference_by_idx = build_slot_preference_index(slots=slots)
    weighted_terms = []

    for s_idx, session in enumerate(sessions):
        for p_idx, slot_key in slot_preference_by_idx.items():
            state = session_preference_state(
                session=session,
                slot_preference_key=slot_key,
            )
            if state == SubjectTimePreferenceState.PREFER_YES:
                weighted_terms.append(PREFER_YES_WEIGHT * x[(s_idx, p_idx)])
            elif state == SubjectTimePreferenceState.PREFER_NO:
                weighted_terms.append(PREFER_NO_WEIGHT * x[(s_idx, p_idx)])

    return weighted_terms


def _tc_session_indices(*, sessions):
    tc_indices = []
    for s_idx, session in enumerate(sessions):
        subject = session.get("subject")
        if getattr(subject, "type", None) == "TC":
            tc_indices.append(s_idx)
    return tc_indices
