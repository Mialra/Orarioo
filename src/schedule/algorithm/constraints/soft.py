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
TEACHER_GAP_PENALTY_WEIGHT = 4


def apply_soft_constraints(*, model, x, sessions, slots, extra_objective_terms=None):
    """Apply optional optimization goals without breaking hard constraints."""
    objective_terms = []
    objective_terms.extend(
        _tc_distribution_terms(model=model, x=x, sessions=sessions, slots=slots)
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
    if extra_objective_terms:
        objective_terms.extend(extra_objective_terms)

    if objective_terms:
        model.Maximize(sum(objective_terms))


def _tc_distribution_terms(*, model, x, sessions, slots):
    """Optimize TC coverage and avoid concentration patterns."""
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
    """Reward covering distinct real-time intervals before stacking TC sessions."""
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


def _tc_sessions_by_teacher(*, sessions, tc_session_indices):
    sessions_by_teacher = {}
    for s_idx in tc_session_indices:
        teacher_id = sessions[s_idx].get("teacher_id")
        if teacher_id is None:
            continue
        sessions_by_teacher.setdefault(teacher_id, []).append(s_idx)
    return sessions_by_teacher


def _tc_candidate_real_intervals(*, slots, candidate_slot_indices):
    return build_real_time_intervals(
        slots=slots,
        slot_indices=candidate_slot_indices,
    )


def _build_slots_by_day(*, slots):
    slot_day_index = build_slot_day_index(slots=slots)
    slots_by_day = {}
    for slot_idx, day_idx in slot_day_index.items():
        slots_by_day.setdefault(day_idx, []).append(slot_idx)
    for day_idx in slots_by_day:
        slots_by_day[day_idx].sort(key=lambda idx: slot_time_bounds(slot=slots[idx])[0])
    return slots_by_day


def _bind_has_any(*, model, expr, bool_var):
    model.Add(expr >= 1).OnlyEnforceIf(bool_var)
    model.Add(expr == 0).OnlyEnforceIf(bool_var.Not())
