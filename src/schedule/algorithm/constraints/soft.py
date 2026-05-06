"""Soft constraints (objective terms) for the CP-SAT schedule optimisation model.

All functions in this module build weighted objective terms that are maximised
after a feasible solution has been found.  They never make the model infeasible.
"""

from schedule.algorithm.constraints.hard import (
    session_preference_state,
    teacher_preference_state,
)
from schedule.algorithm.slots import (
    build_real_time_intervals,
    build_slot_day_index,
    build_slot_preference_index,
    build_stage_allowed_slot_index,
    session_stage_code,
    slot_time_bounds,
)
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState

TC_REAL_INTERVAL_COVERAGE_WEIGHT = 24
TC_REAL_INTERVAL_OVERLOAD_PENALTY_WEIGHT = 8
TC_TEACHER_DAY_SPREAD_WEIGHT = 2
TC_TEACHER_CONSECUTIVE_PENALTY_WEIGHT = 6
PREFER_YES_WEIGHT = 2
PREFER_NO_WEIGHT = -2
TEACHER_PREFER_YES_WEIGHT = 2
TEACHER_PREFER_NO_WEIGHT = -2
SUBJECT_DAY_SPREAD_WEIGHT = 3
TEACHER_GAP_PENALTY_WEIGHT = 8


def apply_soft_constraints(
    *, model, x, sessions, slots, generation_options=None, extra_objective_terms=None
):
    """Collect all soft objective terms and set the model's maximisation objective.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts;
           generation_options - dict of generation parameters controlling which terms to include;
           extra_objective_terms - optional list of additional weighted CP-SAT expressions
    Output: None; side-effect: calls model.Maximize with the combined objective
    """
    opts = generation_options or {}
    objective_terms = []

    if opts.get("enable_tc_distribution", True):
        objective_terms.extend(
            _tc_distribution_terms(model=model, x=x, sessions=sessions, slots=slots)
        )
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
    if extra_objective_terms:
        objective_terms.extend(extra_objective_terms)

    if objective_terms:
        model.Maximize(sum(objective_terms))


def _tc_distribution_terms(*, model, x, sessions, slots):
    """Build objective terms that optimise TC session coverage and spread.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: list of weighted CP-SAT expressions; empty list if no TC sessions exist
    """
    tc_session_indices = _tc_session_indices(sessions=sessions)
    if not tc_session_indices:
        return []

    tc_candidate_slots = _tc_candidate_slot_indices(
        sessions=sessions,
        slots=slots,
        tc_session_indices=tc_session_indices,
    )
    if not tc_candidate_slots:
        return []

    weighted_terms = _tc_real_interval_coverage_terms(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        tc_session_indices=tc_session_indices,
        tc_candidate_slots=tc_candidate_slots,
    )
    weighted_terms.extend(
        _tc_teacher_day_spread_terms(
            model=model,
            x=x,
            sessions=sessions,
            slots=slots,
            tc_session_indices=tc_session_indices,
        )
    )
    weighted_terms.extend(
        _tc_teacher_consecutive_penalty_terms(
            model=model,
            x=x,
            sessions=sessions,
            slots=slots,
            tc_session_indices=tc_session_indices,
        )
    )

    return weighted_terms


def _tc_real_interval_coverage_terms(
    *, model, x, sessions, slots, tc_session_indices, tc_candidate_slots
):
    """Reward covering distinct real-time intervals before stacking TC sessions.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions, slots - standard inputs; tc_session_indices - list of TC session indices;
           tc_candidate_slots - list of candidate slot indices for TC
    Output: list of weighted CP-SAT expressions
    """
    candidate_intervals = _tc_candidate_real_intervals(
        slots=slots,
        candidate_slot_indices=tc_candidate_slots,
    )
    if not candidate_intervals:
        return []

    weighted_terms = []
    for interval in candidate_intervals:
        interval_expr = sum(
            x[(s_idx, p_idx)]
            for s_idx in tc_session_indices
            for p_idx in interval["slot_indices"]
        )
        label = (
            f"d{interval['day_idx']}_{interval['start']:%H%M}_{interval['end']:%H%M}"
        )
        has_tc_in_interval = model.NewBoolVar(f"tc_real_covered_{label}")
        overflow = model.NewIntVar(
            0,
            len(tc_session_indices),
            f"tc_real_overflow_{label}",
        )

        _bind_has_any(
            model=model,
            expr=interval_expr,
            bool_var=has_tc_in_interval,
        )
        model.Add(overflow == interval_expr - has_tc_in_interval)

        weighted_terms.append(TC_REAL_INTERVAL_COVERAGE_WEIGHT * has_tc_in_interval)
        weighted_terms.append(-TC_REAL_INTERVAL_OVERLOAD_PENALTY_WEIGHT * overflow)

    return weighted_terms


def _tc_teacher_day_spread_terms(*, model, x, sessions, slots, tc_session_indices):
    """Reward distributing each teacher's TC sessions across different weekdays.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions, slots - standard inputs; tc_session_indices - list of TC session indices
    Output: list of weighted CP-SAT BoolVar expressions
    """
    slots_by_day = _build_slots_by_day(slots=slots)
    tc_by_teacher = _tc_sessions_by_teacher(
        sessions=sessions,
        tc_session_indices=tc_session_indices,
    )

    weighted_terms = []
    for teacher_id, teacher_tc_sessions in tc_by_teacher.items():
        if len(teacher_tc_sessions) < 2:
            continue

        for day_idx, day_slots in slots_by_day.items():
            tc_on_day_expr = sum(
                x[(s_idx, p_idx)]
                for s_idx in teacher_tc_sessions
                for p_idx in day_slots
            )
            has_tc_day = model.NewBoolVar(f"tc_t{teacher_id}_d{day_idx}_has")
            _bind_has_any(model=model, expr=tc_on_day_expr, bool_var=has_tc_day)
            weighted_terms.append(TC_TEACHER_DAY_SPREAD_WEIGHT * has_tc_day)

    return weighted_terms


def _tc_teacher_consecutive_penalty_terms(
    *, model, x, sessions, slots, tc_session_indices
):
    """Penalise consecutive TC sessions for the same teacher on the same day.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions, slots - standard inputs; tc_session_indices - list of TC session indices
    Output: list of negative weighted CP-SAT BoolVar expressions (penalties)
    """
    slots_by_day = _build_slots_by_day(slots=slots)
    tc_by_teacher = _tc_sessions_by_teacher(
        sessions=sessions,
        tc_session_indices=tc_session_indices,
    )

    weighted_terms = []
    for teacher_id, teacher_tc_sessions in tc_by_teacher.items():
        for day_idx, day_slots in slots_by_day.items():
            if len(day_slots) < 2:
                continue

            has_tc_by_slot = {}
            for p_idx in day_slots:
                tc_in_slot_for_teacher = sum(
                    x[(s_idx, p_idx)] for s_idx in teacher_tc_sessions
                )
                has_tc = model.NewBoolVar(f"tc_t{teacher_id}_d{day_idx}_p{p_idx}_has")
                _bind_has_any(
                    model=model,
                    expr=tc_in_slot_for_teacher,
                    bool_var=has_tc,
                )
                has_tc_by_slot[p_idx] = has_tc

            for left_slot, right_slot in zip(day_slots, day_slots[1:]):
                is_consecutive_tc = model.NewBoolVar(
                    f"tc_t{teacher_id}_d{day_idx}_{left_slot}_{right_slot}_cons"
                )
                model.AddBoolAnd(
                    [has_tc_by_slot[left_slot], has_tc_by_slot[right_slot]]
                ).OnlyEnforceIf(is_consecutive_tc)
                model.AddBoolOr(
                    [
                        has_tc_by_slot[left_slot].Not(),
                        has_tc_by_slot[right_slot].Not(),
                    ]
                ).OnlyEnforceIf(is_consecutive_tc.Not())
                weighted_terms.append(
                    -TC_TEACHER_CONSECUTIVE_PENALTY_WEIGHT * is_consecutive_tc
                )

    return weighted_terms


def _tc_candidate_slot_indices(*, sessions, slots, tc_session_indices):
    """Return the sorted list of slot indices that TC sessions are allowed to use.
    Input: sessions - list of session dicts; slots - list of slot dicts;
           tc_session_indices - list of TC session indices
    Output: sorted list of slot indices available to TC sessions (after stage and preference filtering)
    """
    allowed_slots_by_stage = build_stage_allowed_slot_index(slots=slots)
    slot_preference_by_idx = build_slot_preference_index(slots=slots)

    candidate_slots = set()
    for s_idx in tc_session_indices:
        session = sessions[s_idx]
        stage_code = session_stage_code(session=session)
        stage_allowed = allowed_slots_by_stage.get(stage_code, set())

        for p_idx in stage_allowed:
            preference_key = slot_preference_by_idx.get(p_idx)
            if preference_key is None:
                continue

            subject_state = session_preference_state(
                session=session,
                slot_preference_key=preference_key,
            )
            if subject_state == SubjectTimePreferenceState.UNAVAILABLE:
                continue

            teacher_state = teacher_preference_state(
                session=session,
                slot_preference_key=preference_key,
            )
            if teacher_state == TeacherTimePreferenceState.UNAVAILABLE:
                continue

            candidate_slots.add(p_idx)

    return sorted(candidate_slots)


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
        prefer_no_weight=PREFER_NO_WEIGHT,
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

        for day_idx, day_slot_list in slots_by_day.items():
            if len(day_slot_list) < 3:
                continue

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
    """Return the indices of sessions whose subject type is TC.
    Input: sessions - list of session dicts
    Output: list of integer session indices
    """
    tc_indices = []
    for s_idx, session in enumerate(sessions):
        subject = session.get("subject")
        if getattr(subject, "type", None) == "TC":
            tc_indices.append(s_idx)
    return tc_indices


def _tc_sessions_by_teacher(*, sessions, tc_session_indices):
    """Group TC session indices by teacher id.
    Input: sessions - list of session dicts; tc_session_indices - list of TC session indices
    Output: dict {teacher_id: [session_idx, ...]}
    """
    sessions_by_teacher = {}
    for s_idx in tc_session_indices:
        teacher_id = sessions[s_idx].get("teacher_id")
        if teacher_id is None:
            continue
        sessions_by_teacher.setdefault(teacher_id, []).append(s_idx)
    return sessions_by_teacher


def _tc_candidate_real_intervals(*, slots, candidate_slot_indices):
    """Return the real-time intervals covering the given TC candidate slot indices.
    Input: slots - full list of slot dicts; candidate_slot_indices - list of slot indices
    Output: list of interval dicts from build_real_time_intervals
    """
    return build_real_time_intervals(
        slots=slots,
        slot_indices=candidate_slot_indices,
    )


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

    if opts.get("enable_tc_distribution", True):
        score = _eval_tc_distribution_score(
            slot_by_session=slot_by_session, sessions=sessions, slots=slots
        )
        breakdown["tc_distribution"] = score
        total += score

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

    teacher_slots_by_day = {}
    for s_idx, session in enumerate(sessions):
        teacher_id = session.get("teacher_id")
        if teacher_id is None:
            continue
        assigned = slot_by_session[s_idx]
        day_idx = slot_day_index.get(assigned)
        if day_idx is None:
            continue
        teacher_slots_by_day.setdefault(teacher_id, {}).setdefault(day_idx, set()).add(
            assigned
        )

    total = 0
    for _teacher_id, days in teacher_slots_by_day.items():
        for day_idx, day_slot_list in slots_by_day.items():
            if len(day_slot_list) < 3:
                continue
            assigned_in_day = days.get(day_idx, set())
            for inner_pos, p_i in enumerate(day_slot_list[1:-1], start=1):
                before_slots = set(day_slot_list[:inner_pos])
                after_slots = set(day_slot_list[inner_pos + 1 :])
                has_before = bool(assigned_in_day & before_slots)
                has_after = bool(assigned_in_day & after_slots)
                has_at = p_i in assigned_in_day
                if has_before and has_after and not has_at:
                    total -= TEACHER_GAP_PENALTY_WEIGHT
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
            total += PREFER_NO_WEIGHT
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
            total += TEACHER_PREFER_NO_WEIGHT
    return total


def _eval_tc_distribution_score(*, slot_by_session, sessions, slots):
    """Compute the TC distribution score for a concrete assignment.
    Mirrors _tc_distribution_terms: coverage reward, overload penalty, spread, consecutive penalty.
    """
    tc_session_indices = [
        s_idx
        for s_idx, session in enumerate(sessions)
        if getattr(session.get("subject"), "type", None) == "TC"
    ]
    if not tc_session_indices:
        return 0

    total = _eval_tc_interval_coverage(
        slot_by_session=slot_by_session,
        slots=slots,
        tc_session_indices=tc_session_indices,
    )
    total += _eval_tc_teacher_spread_and_consecutive(
        slot_by_session=slot_by_session,
        sessions=sessions,
        slots=slots,
        tc_session_indices=tc_session_indices,
    )
    return total


def _eval_tc_interval_coverage(*, slot_by_session, slots, tc_session_indices):
    """Reward unique real-time interval coverage and penalise overload for TC sessions."""
    real_time_intervals = build_real_time_intervals(slots=slots)
    total = 0
    for interval in real_time_intervals:
        interval_slots = set(interval["slot_indices"])
        tc_count = sum(
            1
            for s_idx in tc_session_indices
            if slot_by_session[s_idx] in interval_slots
        )
        if tc_count > 0:
            total += TC_REAL_INTERVAL_COVERAGE_WEIGHT
            total -= TC_REAL_INTERVAL_OVERLOAD_PENALTY_WEIGHT * (tc_count - 1)
    return total


def _eval_tc_teacher_spread_and_consecutive(
    *, slot_by_session, sessions, slots, tc_session_indices
):
    """Reward day spread and penalise consecutive TC sessions per teacher."""
    slots_by_day = _build_slots_by_day(slots=slots)
    tc_by_teacher = _tc_sessions_by_teacher(
        sessions=sessions, tc_session_indices=tc_session_indices
    )
    total = 0
    for _teacher_id, teacher_tc_sessions in tc_by_teacher.items():
        if len(teacher_tc_sessions) < 2:
            continue
        for day_slot_list in slots_by_day.values():
            total += _eval_tc_teacher_day(
                slot_by_session=slot_by_session,
                teacher_tc_sessions=teacher_tc_sessions,
                day_slot_list=day_slot_list,
            )
    return total


def _eval_tc_teacher_day(*, slot_by_session, teacher_tc_sessions, day_slot_list):
    """Compute spread bonus and consecutive penalty for one teacher on one day."""
    day_slots_set = set(day_slot_list)
    has_tc = any(
        slot_by_session[s_idx] in day_slots_set for s_idx in teacher_tc_sessions
    )
    total = TC_TEACHER_DAY_SPREAD_WEIGHT if has_tc else 0

    if len(day_slot_list) < 2:
        return total

    has_tc_in_slot = {
        p: any(slot_by_session[s_idx] == p for s_idx in teacher_tc_sessions)
        for p in day_slot_list
    }
    for left_slot, right_slot in zip(day_slot_list, day_slot_list[1:]):
        if has_tc_in_slot[left_slot] and has_tc_in_slot[right_slot]:
            total -= TC_TEACHER_CONSECUTIVE_PENALTY_WEIGHT
    return total
