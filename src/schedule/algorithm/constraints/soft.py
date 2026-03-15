def apply_soft_constraints(*, model, x, sessions, slots):
    """Apply optional optimization goals without breaking hard constraints."""
    _maximize_tc_slot_coverage(model=model, x=x, sessions=sessions, slots=slots)


def _maximize_tc_slot_coverage(*, model, x, sessions, slots):
    """
    Spread TC sessions across as many weekly slots as possible.

    This increases the chance of having at least one teacher in guard duty
    (TC) available in more moments of the timetable whenever feasible.
    """
    tc_session_indices = _tc_session_indices(sessions=sessions)
    if not tc_session_indices:
        return

    slot_covered_vars = []
    for p_idx in range(len(slots)):
        has_tc_in_slot = model.NewBoolVar(f"tc_covered_p{p_idx}")
        tc_in_slot_expr = sum(x[(s_idx, p_idx)] for s_idx in tc_session_indices)

        model.Add(tc_in_slot_expr >= 1).OnlyEnforceIf(has_tc_in_slot)
        model.Add(tc_in_slot_expr == 0).OnlyEnforceIf(has_tc_in_slot.Not())

        slot_covered_vars.append(has_tc_in_slot)

    model.Maximize(sum(slot_covered_vars))


def _tc_session_indices(*, sessions):
    tc_indices = []
    for s_idx, session in enumerate(sessions):
        subject = session.get("subject")
        if getattr(subject, "type", None) == "TC":
            tc_indices.append(s_idx)
    return tc_indices
