"""Soft constraints (objective terms) for the CP-SAT schedule optimisation model.

All functions in this module build weighted objective terms that are maximised
after a feasible solution has been found.  They never make the model infeasible.
"""

from schedule.algorithm.constraints.hard import (session_preference_state,
                                                 teacher_preference_state)
from schedule.algorithm.slots import (build_slot_day_index,
                                      build_slot_preference_index,
                                      session_stage_code, slot_time_bounds)
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState

PREFER_YES_WEIGHT = 2
PREFER_NO_WEIGHT_PENALTY = 2
TEACHER_PREFER_YES_WEIGHT = 2
TEACHER_PREFER_NO_WEIGHT_PENALTY = 2
SUBJECT_DAY_SPREAD_WEIGHT = 3
TEACHER_GAP_WEIGHT_PENALTY = 8


def apply_soft_constraints(*, model, x, sessions, slots, generation_options=None):
    """Collect all soft objective terms and set the model's maximisation objective.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts;
           generation_options - dict of generation parameters controlling which terms to include
    Output: None; side-effect: calls model.Maximize with the combined objective
    """
    opts = generation_options or {}
    objective_terms = []

    if opts.get("enable_subject_time_preferences", True):
        objective_terms.extend(
            _subject_time_preference_terms(x=x, sessions=sessions, slots=slots)
        )
    if opts.get("enable_teacher_time_preferences", True):
        objective_terms.extend(
            _teacher_time_preference_terms(x=x, sessions=sessions, slots=slots)
        )
    if opts.get("enable_subject_day_spread", True):
        objective_terms.extend(
            _subject_day_spread_terms(model=model, x=x, sessions=sessions, slots=slots)
        )
    if opts.get("enable_teacher_gap_minimization", True):
        objective_terms.extend(
            _teacher_gap_minimization_terms(
                model=model, x=x, sessions=sessions, slots=slots
            )
        )

    if objective_terms:
        model.Maximize(sum(objective_terms))


def _subject_time_preference_terms(*, x, sessions, slots):
    """Build objective terms for subject time preferences (PREFER_YES / PREFER_NO).
    Input: x - slot decision variables; sessions - list of session dicts; slots - list of slot dicts
    Output: list of weighted CP-SAT expressions
    """
    return _preference_terms(
        x=x,
        sessions=sessions,
        slots=slots,
        state_resolver=session_preference_state,
        prefer_yes_state=SubjectTimePreferenceState.PREFER_YES,
        prefer_no_state=SubjectTimePreferenceState.PREFER_NO,
        prefer_yes_weight=PREFER_YES_WEIGHT,
        prefer_no_weight=-PREFER_NO_WEIGHT_PENALTY,
    )


def _teacher_time_preference_terms(*, x, sessions, slots):
    """Build objective terms for teacher time preferences (PREFER_YES / PREFER_NO).
    Input: x - slot decision variables; sessions - list of session dicts; slots - list of slot dicts
    Output: list of weighted CP-SAT expressions
    """
    return _preference_terms(
        x=x,
        sessions=sessions,
        slots=slots,
        state_resolver=teacher_preference_state,
        prefer_yes_state=TeacherTimePreferenceState.PREFER_YES,
        prefer_no_state=TeacherTimePreferenceState.PREFER_NO,
        prefer_yes_weight=TEACHER_PREFER_YES_WEIGHT,
        prefer_no_weight=-TEACHER_PREFER_NO_WEIGHT_PENALTY,
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
    """Build weighted objective terms from time-preference states for all sessions and slots.
    Input: x - slot decision variables; sessions - list of session dicts; slots - list of slot dicts;
           state_resolver - callable(session, slot_preference_key) → state;
           prefer_yes_state, prefer_no_state - state values to reward/penalise;
           prefer_yes_weight, prefer_no_weight - corresponding integer weights
    Output: list of weighted CP-SAT expressions
    """
    slot_preference_by_idx = build_slot_preference_index(slots=slots)
    weighted_terms = []

    for s_idx, session in enumerate(sessions):
        for p_idx, slot_key in slot_preference_by_idx.items():
            if (s_idx, p_idx) not in x:
                continue
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
    """Reward distributing sessions of the same subject across different weekdays.

    For each subject with more than one session, a bonus is added for each
    distinct weekday that has at least one session assigned to it.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: list of weighted CP-SAT BoolVar expressions
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
                x[(s_idx, p_idx)]
                for s_idx in s_indices
                for p_idx in day_slots
                if (s_idx, p_idx) in x
            )
            _bind_has_any(
                model=model,
                expr=sessions_on_day_expr,
                bool_var=has_session_on_day,
            )
            weighted_terms.append(SUBJECT_DAY_SPREAD_WEIGHT * has_session_on_day)

    return weighted_terms


def _teacher_gap_minimization_terms(*, model, x, sessions, slots):
    """Penalise intra-day gaps in a teacher's schedule (F-29).

    A gap occurs when a teacher has sessions both before and after a slot on the
    same day but nothing in that slot itself.  Only inner slots are penalised;
    free time at the edges of a teacher's workday is not counted.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: list of negative weighted CP-SAT BoolVar expressions (penalties)
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

        t_stages = {
            session_stage_code(session=sessions[s_idx]) for s_idx in t_session_indices
        }

        for day_idx, raw_day_slots in slots_by_day.items():
            day_slot_list = [
                p
                for p in raw_day_slots
                if slots[p].get("stage") in t_stages
                and not slots[p].get("is_recess", False)
            ]
            if len(day_slot_list) < 3:
                continue

            for inner_pos, p_i in enumerate(day_slot_list[1:-1], start=1):
                before_slots = day_slot_list[:inner_pos]
                after_slots = day_slot_list[inner_pos + 1 :]

                n_before = sum(
                    x[(s_idx, p_j)]
                    for s_idx in t_session_indices
                    for p_j in before_slots
                    if (s_idx, p_j) in x
                )
                n_after = sum(
                    x[(s_idx, p_j)]
                    for s_idx in t_session_indices
                    for p_j in after_slots
                    if (s_idx, p_j) in x
                )
                n_at = sum(
                    x[(s_idx, p_i)] for s_idx in t_session_indices if (s_idx, p_i) in x
                )

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

                weighted_terms.append(-TEACHER_GAP_WEIGHT_PENALTY * is_gap)

    return weighted_terms


def _build_slots_by_day(*, slots):
    """Group slot indices by day index, sorted by start time within each day.
    Input: slots - list of slot dicts
    Output: dict {day_idx: [slot_idx, ...]} sorted by slot start time
    """
    slot_day_index = build_slot_day_index(slots=slots)
    slots_by_day = {}
    for slot_idx, day_idx in slot_day_index.items():
        slots_by_day.setdefault(day_idx, []).append(slot_idx)
    for day_idx in slots_by_day:
        slots_by_day[day_idx].sort(key=lambda idx: slot_time_bounds(slot=slots[idx])[0])
    return slots_by_day


def _bind_has_any(*, model, expr, bool_var):
    """Link a BoolVar to whether a linear expression is >= 1.
    Input: model - CP-SAT CpModel; expr - linear CP-SAT expression; bool_var - BoolVar to bind
    Output: None; side-effect: adds two enforcement constraints to model
    """
    model.Add(expr >= 1).OnlyEnforceIf(bool_var)
    model.Add(expr == 0).OnlyEnforceIf(bool_var.Not())


# ---------------------------------------------------------------------------
# Pure-Python score evaluation (no CP-SAT required)
# ---------------------------------------------------------------------------


def evaluate_soft_score(*, slot_by_session, sessions, slots, generation_options=None):
    """Compute the soft constraint score for a concrete assignment without CP-SAT.

    Replicates the weighted objective terms from apply_soft_constraints so that
    the Phase 1 (feasibility) and Phase 2 (optimised) solutions can be compared.
    Input: slot_by_session - list[int] mapping session index → assigned slot index;
           sessions - list of session dicts; slots - list of slot dicts;
           generation_options - dict controlling which terms are active
    Output: dict {total: int, breakdown: {component: int}}
    """
    opts = generation_options or {}
    total = 0
    breakdown = {}

    if opts.get("enable_subject_time_preferences", True):
        score = _eval_subject_time_preference_score(
            slot_by_session=slot_by_session, sessions=sessions, slots=slots
        )
        breakdown["subject_preferences"] = score
        total += score

    if opts.get("enable_teacher_time_preferences", True):
        score = _eval_teacher_time_preference_score(
            slot_by_session=slot_by_session, sessions=sessions, slots=slots
        )
        breakdown["teacher_preferences"] = score
        total += score

    if opts.get("enable_subject_day_spread", True):
        score = _eval_subject_day_spread_score(
            slot_by_session=slot_by_session, sessions=sessions, slots=slots
        )
        breakdown["subject_spread"] = score
        total += score

    if opts.get("enable_teacher_gap_minimization", True):
        score = _eval_teacher_gap_score(
            slot_by_session=slot_by_session, sessions=sessions, slots=slots
        )
        breakdown["teacher_gaps"] = score
        total += score

    return {"total": total, "breakdown": breakdown}


def _eval_teacher_gap_score(*, slot_by_session, sessions, slots):
    """Compute the teacher gap penalty for a concrete assignment.
    Mirrors _teacher_gap_minimization_terms: -TEACHER_GAP_PENALTY_WEIGHT per inner gap.
    """
    slot_day_index = build_slot_day_index(slots=slots)
    slots_by_day = _build_slots_by_day(slots=slots)

    teacher_stages = {}
    teacher_slots_by_day = {}
    for s_idx, session in enumerate(sessions):
        teacher_id = session.get("teacher_id")
        if teacher_id is None:
            continue
        assigned = slot_by_session[s_idx]
        day_idx = slot_day_index.get(assigned)
        if day_idx is None:
            continue
        stage = slots[assigned].get("stage")
        teacher_stages.setdefault(teacher_id, set()).add(stage)
        teacher_slots_by_day.setdefault(teacher_id, {}).setdefault(day_idx, set()).add(
            assigned
        )

    total = 0
    for teacher_id, days in teacher_slots_by_day.items():
        t_stages = teacher_stages.get(teacher_id, set())
        for day_idx, assigned_in_day in days.items():
            day_slot_list = [
                idx
                for idx in slots_by_day.get(day_idx, [])
                if slots[idx].get("stage") in t_stages
                and not slots[idx].get("is_recess", False)
            ]
            if len(day_slot_list) < 3:
                continue
            for inner_pos, p_i in enumerate(day_slot_list[1:-1], start=1):
                before_slots = set(day_slot_list[:inner_pos])
                after_slots = set(day_slot_list[inner_pos + 1 :])
                has_before = bool(assigned_in_day & before_slots)
                has_after = bool(assigned_in_day & after_slots)
                has_at = p_i in assigned_in_day
                if has_before and has_after and not has_at:
                    total -= TEACHER_GAP_WEIGHT_PENALTY
    return total


def _eval_subject_day_spread_score(*, slot_by_session, sessions, slots):
    """Compute the subject day-spread bonus for a concrete assignment.
    Mirrors _subject_day_spread_terms: +SUBJECT_DAY_SPREAD_WEIGHT per (subject, day) covered.
    """
    slot_day_index = build_slot_day_index(slots=slots)
    sessions_by_subject = {}
    for s_idx, session in enumerate(sessions):
        subject = session.get("subject")
        if subject is not None:
            sessions_by_subject.setdefault(subject.id, []).append(s_idx)

    total = 0
    for _subj_id, s_indices in sessions_by_subject.items():
        if len(s_indices) < 2:
            continue
        days_covered = set()
        for s_idx in s_indices:
            day_idx = slot_day_index.get(slot_by_session[s_idx])
            if day_idx is not None:
                days_covered.add(day_idx)
        total += SUBJECT_DAY_SPREAD_WEIGHT * len(days_covered)
    return total


def _eval_subject_time_preference_score(*, slot_by_session, sessions, slots):
    """Compute the subject time-preference score for a concrete assignment."""
    slot_preference_by_idx = build_slot_preference_index(slots=slots)
    total = 0
    for s_idx, session in enumerate(sessions):
        slot_key = slot_preference_by_idx.get(slot_by_session[s_idx])
        if slot_key is None:
            continue
        state = session_preference_state(session=session, slot_preference_key=slot_key)
        if state == SubjectTimePreferenceState.PREFER_YES:
            total += PREFER_YES_WEIGHT
        elif state == SubjectTimePreferenceState.PREFER_NO:
            total -= PREFER_NO_WEIGHT_PENALTY
    return total


def _eval_teacher_time_preference_score(*, slot_by_session, sessions, slots):
    """Compute the teacher time-preference score for a concrete assignment."""
    slot_preference_by_idx = build_slot_preference_index(slots=slots)
    total = 0
    for s_idx, session in enumerate(sessions):
        slot_key = slot_preference_by_idx.get(slot_by_session[s_idx])
        if slot_key is None:
            continue
        state = teacher_preference_state(session=session, slot_preference_key=slot_key)
        if state == TeacherTimePreferenceState.PREFER_YES:
            total += TEACHER_PREFER_YES_WEIGHT
        elif state == TeacherTimePreferenceState.PREFER_NO:
            total -= TEACHER_PREFER_NO_WEIGHT_PENALTY
    return total
