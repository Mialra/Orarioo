from schedule.algorithm.constraints.hard import (
    session_preference_state,
    teacher_preference_state,
)
from schedule.algorithm.slots import build_slot_day_index, build_slot_preference_index
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState

TC_SLOT_COVERAGE_WEIGHT = 5
PREFER_YES_WEIGHT = 2
PREFER_NO_WEIGHT = -2
TEACHER_PREFER_YES_WEIGHT = 2
TEACHER_PREFER_NO_WEIGHT = -2
SUBJECT_DAY_SPREAD_WEIGHT = 3
TEACHER_GAP_PENALTY_WEIGHT = 4


def apply_soft_constraints(*, model, x, sessions, slots):
    """Apply optional optimization goals without breaking hard constraints."""
    objective_terms = []
    objective_terms.extend(
        _tc_slot_coverage_terms(model=model, x=x, sessions=sessions, slots=slots)
    )
    objective_terms.extend(
        _subject_time_preference_terms(x=x, sessions=sessions, slots=slots)
    )
    objective_terms.extend(
        _teacher_time_preference_terms(x=x, sessions=sessions, slots=slots)
    )
    objective_terms.extend(
        _subject_day_spread_terms(model=model, x=x, sessions=sessions, slots=slots)
    )
    objective_terms.extend(
        _teacher_gap_minimization_terms(
            model=model, x=x, sessions=sessions, slots=slots
        )
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
    return _preference_terms(
        x=x,
        sessions=sessions,
        slots=slots,
        state_resolver=session_preference_state,
        prefer_yes_state=SubjectTimePreferenceState.PREFER_YES,
        prefer_no_state=SubjectTimePreferenceState.PREFER_NO,
        prefer_yes_weight=PREFER_YES_WEIGHT,
        prefer_no_weight=PREFER_NO_WEIGHT,
    )


def _teacher_time_preference_terms(*, x, sessions, slots):
    return _preference_terms(
        x=x,
        sessions=sessions,
        slots=slots,
        state_resolver=teacher_preference_state,
        prefer_yes_state=TeacherTimePreferenceState.PREFER_YES,
        prefer_no_state=TeacherTimePreferenceState.PREFER_NO,
        prefer_yes_weight=TEACHER_PREFER_YES_WEIGHT,
        prefer_no_weight=TEACHER_PREFER_NO_WEIGHT,
    )


def _preference_terms(
    *,
    x,
    sessions,
    slots,
    state_resolver,
    prefer_yes_state,
    prefer_no_state,
    prefer_yes_weight,
    prefer_no_weight,
):
    slot_preference_by_idx = build_slot_preference_index(slots=slots)
    weighted_terms = []

    for s_idx, session in enumerate(sessions):
        for p_idx, slot_key in slot_preference_by_idx.items():
            state = state_resolver(
                session=session,
                slot_preference_key=slot_key,
            )
            if state == prefer_yes_state:
                weighted_terms.append(prefer_yes_weight * x[(s_idx, p_idx)])
            elif state == prefer_no_state:
                weighted_terms.append(prefer_no_weight * x[(s_idx, p_idx)])

    return weighted_terms


def _subject_day_spread_terms(*, model, x, sessions, slots):
    """
    Reward distributing sessions of the same subject across different weekdays.

    For each subject with more than one session, a bonus is added for each
    distinct weekday that has at least one session assigned to it. This
    encourages the solver to avoid concentrating all sessions in a few days.
    """
    slots_by_day = _build_slots_by_day(slots=slots)

    sessions_by_subject = {}
    for s_idx, session in enumerate(sessions):
        subject = session.get("subject")
        if subject is not None:
            sessions_by_subject.setdefault(subject.id, []).append(s_idx)

    weighted_terms = []
    for subj_id, s_indices in sessions_by_subject.items():
        if len(s_indices) < 2:
            continue
        for day_idx, day_slots in slots_by_day.items():
            has_session_on_day = model.NewBoolVar(f"subj{subj_id}_day{day_idx}")
            sessions_on_day_expr = sum(
                x[(s_idx, p_idx)] for s_idx in s_indices for p_idx in day_slots
            )
            _bind_has_any(
                model=model,
                expr=sessions_on_day_expr,
                bool_var=has_session_on_day,
            )
            weighted_terms.append(SUBJECT_DAY_SPREAD_WEIGHT * has_session_on_day)

    return weighted_terms


def _teacher_gap_minimization_terms(*, model, x, sessions, slots):
    """
    Penalize intra-day gaps in a teacher's schedule (F-29).

    A gap occurs when a teacher has sessions assigned both before and after a
    particular time slot on the same day, but nothing in that slot itself.
    Only inner slots (not the first or last slot of the day) are penalised,
    so free time at the edges of a teacher's workday is not counted.
    """
    slots_by_day = _build_slots_by_day(slots=slots)

    sessions_by_teacher = {}
    for s_idx, session in enumerate(sessions):
        teacher_id = session.get("teacher_id")
        if teacher_id is not None:
            sessions_by_teacher.setdefault(teacher_id, []).append(s_idx)

    weighted_terms = []
    for teacher_id, t_session_indices in sessions_by_teacher.items():
        if len(t_session_indices) < 2:
            continue

        for day_idx, day_slot_list in slots_by_day.items():
            if len(day_slot_list) < 3:
                continue

            # Check each inner slot (neither first nor last of the day).
            for inner_pos, p_i in enumerate(day_slot_list[1:-1], start=1):
                before_slots = day_slot_list[:inner_pos]
                after_slots = day_slot_list[inner_pos + 1 :]

                n_before = sum(
                    x[(s_idx, p_j)]
                    for s_idx in t_session_indices
                    for p_j in before_slots
                )
                n_after = sum(
                    x[(s_idx, p_j)]
                    for s_idx in t_session_indices
                    for p_j in after_slots
                )
                n_at = sum(x[(s_idx, p_i)] for s_idx in t_session_indices)

                has_before = model.NewBoolVar(f"t{teacher_id}_d{day_idx}_p{p_i}_before")
                has_after = model.NewBoolVar(f"t{teacher_id}_d{day_idx}_p{p_i}_after")
                has_at = model.NewBoolVar(f"t{teacher_id}_d{day_idx}_p{p_i}_at")

                _bind_has_any(model=model, expr=n_before, bool_var=has_before)
                _bind_has_any(model=model, expr=n_after, bool_var=has_after)
                _bind_has_any(model=model, expr=n_at, bool_var=has_at)

                is_gap = model.NewBoolVar(f"t{teacher_id}_d{day_idx}_p{p_i}_gap")
                model.AddBoolAnd([has_before, has_after, has_at.Not()]).OnlyEnforceIf(
                    is_gap
                )
                model.AddBoolOr(
                    [has_before.Not(), has_after.Not(), has_at]
                ).OnlyEnforceIf(is_gap.Not())

                weighted_terms.append(-TEACHER_GAP_PENALTY_WEIGHT * is_gap)

    return weighted_terms


def _tc_session_indices(*, sessions):
    tc_indices = []
    for s_idx, session in enumerate(sessions):
        subject = session.get("subject")
        if getattr(subject, "type", None) == "TC":
            tc_indices.append(s_idx)
    return tc_indices


def _build_slots_by_day(*, slots):
    slot_day_index = build_slot_day_index(slots=slots)
    slots_by_day = {}
    for slot_idx, day_idx in slot_day_index.items():
        slots_by_day.setdefault(day_idx, []).append(slot_idx)
    for day_idx in slots_by_day:
        slots_by_day[day_idx].sort()
    return slots_by_day


def _bind_has_any(*, model, expr, bool_var):
    model.Add(expr >= 1).OnlyEnforceIf(bool_var)
    model.Add(expr == 0).OnlyEnforceIf(bool_var.Not())
