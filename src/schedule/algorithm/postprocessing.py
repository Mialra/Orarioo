"""Greedy post-processing to compact teacher schedules after CP-SAT.

Runs hill-climbing moves that shift individual sessions into intraday gap
slots, reducing teacher gaps without violating hard constraints.
"""

import time

from schedule.algorithm.slots import (
    build_slot_day_index,
    build_stage_allowed_slot_index,
    session_stage_code,
    slot_time_bounds,
)


def apply_teacher_gap_local_search(
    *,
    slot_by_session,
    classroom_by_session,
    sessions,
    slots,
    fixed_assignments=None,
    max_passes=3,
    deadline=None,
):
    """Reduce teacher intraday gaps via greedy single-session moves.

    For each teacher gap found, tries to move a session from later in the day
    into the gap slot.  Only accepts moves that are hard-constraint-feasible
    (no teacher/group/classroom overlap, stage and recess rules respected).
    Runs up to max_passes over all teachers, stopping early when no move is found.

    Input: slot_by_session - list[int] of assigned slot indices (mutable copy expected);
           classroom_by_session - list[Classroom] of assigned classrooms;
           sessions - list of session dicts; slots - list of slot dicts;
           fixed_assignments - dict {session_idx: slot_idx} of locked assignments;
           max_passes - maximum full passes before stopping (default 3)
    Output: (slot_by_session, classroom_by_session) — same objects, possibly improved
    """
    slot_by_session = list(slot_by_session)
    fixed = set(fixed_assignments or {})

    slot_day_index = build_slot_day_index(slots=slots)
    slots_by_day = _build_slots_by_day(slots=slots, slot_day_index=slot_day_index)
    stage_allowed = build_stage_allowed_slot_index(slots=slots)

    indices = _build_conflict_indices(
        slot_by_session=slot_by_session,
        classroom_by_session=classroom_by_session,
        sessions=sessions,
        slot_day_index=slot_day_index,
    )

    for _ in range(max_passes):
        if deadline is not None and time.monotonic() >= deadline:
            break
        if not _run_single_pass(
            slot_by_session=slot_by_session,
            classroom_by_session=classroom_by_session,
            sessions=sessions,
            slots=slots,
            fixed=fixed,
            slots_by_day=slots_by_day,
            stage_allowed=stage_allowed,
            indices=indices,
            slot_day_index=slot_day_index,
        ):
            break

    return slot_by_session, classroom_by_session


def _run_single_pass(
    *,
    slot_by_session,
    classroom_by_session,
    sessions,
    slots,
    fixed,
    slots_by_day,
    stage_allowed,
    indices,
    slot_day_index,
):
    """Run one full pass over all teachers, attempting gap-filling moves.
    Input: all algorithm state
    Output: True if at least one move was made, False otherwise
    """
    teacher_day_slots = indices["teacher_day_slots"]
    session_by_teacher_day = indices["session_by_teacher_day"]

    any_move = False
    for teacher_id in list(teacher_day_slots):
        for day_idx, day_slot_list in slots_by_day.items():
            if len(day_slot_list) < 3:
                continue
            teacher_day = teacher_day_slots[teacher_id].get(day_idx, set())
            if len(teacher_day) < 2:
                continue

            for inner_pos, gap_slot in enumerate(day_slot_list[1:-1], start=1):
                before = set(day_slot_list[:inner_pos])
                after = set(day_slot_list[inner_pos + 1 :])
                if not (
                    teacher_day & before
                    and teacher_day & after
                    and gap_slot not in teacher_day
                ):
                    continue

                candidate = _find_gap_fill_candidate(
                    gap_slot=gap_slot,
                    after_slots=after,
                    teacher_id=teacher_id,
                    day_idx=day_idx,
                    session_by_teacher_day=session_by_teacher_day,
                    fixed=fixed,
                    sessions=sessions,
                    slots=slots,
                    classroom_by_session=classroom_by_session,
                    stage_allowed=stage_allowed,
                    indices=indices,
                )
                if candidate is None:
                    continue

                s_idx, old_slot = candidate
                _apply_move(
                    s_idx=s_idx,
                    old_slot=old_slot,
                    new_slot=gap_slot,
                    slot_by_session=slot_by_session,
                    sessions=sessions,
                    classroom_by_session=classroom_by_session,
                    indices=indices,
                    slot_day_index=slot_day_index,
                )
                any_move = True
                break

    return any_move


def _find_gap_fill_candidate(
    *,
    gap_slot,
    after_slots,
    teacher_id,
    day_idx,
    session_by_teacher_day,
    fixed,
    sessions,
    slots,
    classroom_by_session,
    stage_allowed,
    indices,
):
    """Return the first (s_idx, old_slot) that can be moved into gap_slot, or None.
    Candidates are sessions of teacher_id that are later in the same day (in after_slots).
    Input: standard local-search state
    Output: (session_idx, current_slot) or None
    """
    group_slot_set = indices["group_slot_set"]
    classroom_slot_set = indices["classroom_slot_set"]

    candidates = session_by_teacher_day.get(teacher_id, {}).get(day_idx, [])
    for s_idx, old_slot in candidates:
        if s_idx in fixed or old_slot not in after_slots:
            continue

        session = sessions[s_idx]
        stage = session_stage_code(session=session)
        group = session.get("group")
        group_id = getattr(group, "id", None)
        classroom = classroom_by_session[s_idx]
        classroom_id = getattr(classroom, "id", None)

        if gap_slot not in stage_allowed.get(stage, set()):
            continue
        if slots[gap_slot].get("is_recess"):
            continue
        if group_id is not None and gap_slot in group_slot_set.get(group_id, set()):
            continue
        if classroom_id is not None and gap_slot in classroom_slot_set.get(
            classroom_id, set()
        ):
            continue

        return s_idx, old_slot

    return None


def _apply_move(
    *,
    s_idx,
    old_slot,
    new_slot,
    slot_by_session,
    sessions,
    classroom_by_session,
    indices,
    slot_day_index,
):
    """Update slot_by_session and all conflict indices after moving a session.
    Input: s_idx - session index; old_slot, new_slot - slot indices;
           slot_by_session - mutable list; sessions, classroom_by_session - algorithm inputs;
           indices - mutable conflict indices dict; slot_day_index - slot→day mapping
    Output: None; side-effect: mutates slot_by_session and indices
    """
    session = sessions[s_idx]
    teacher_id = session.get("teacher_id")
    group = session.get("group")
    group_id = getattr(group, "id", None)
    classroom = classroom_by_session[s_idx]
    classroom_id = getattr(classroom, "id", None)

    old_day = slot_day_index.get(old_slot)
    new_day = slot_day_index.get(new_slot)

    slot_by_session[s_idx] = new_slot

    teacher_day_slots = indices["teacher_day_slots"]
    if teacher_id is not None and old_day is not None:
        teacher_day_slots.setdefault(teacher_id, {}).setdefault(old_day, set()).discard(
            old_slot
        )
    if teacher_id is not None and new_day is not None:
        teacher_day_slots.setdefault(teacher_id, {}).setdefault(new_day, set()).add(
            new_slot
        )

    group_slot_set = indices["group_slot_set"]
    if group_id is not None:
        group_slot_set.setdefault(group_id, set()).discard(old_slot)
        group_slot_set.setdefault(group_id, set()).add(new_slot)

    classroom_slot_set = indices["classroom_slot_set"]
    if classroom_id is not None:
        classroom_slot_set.setdefault(classroom_id, set()).discard(old_slot)
        classroom_slot_set.setdefault(classroom_id, set()).add(new_slot)

    session_by_tday = indices["session_by_teacher_day"]
    if teacher_id is not None:
        if old_day is not None:
            session_by_tday.setdefault(teacher_id, {}).setdefault(old_day, [])
            session_by_tday[teacher_id][old_day] = [
                (si, p) for si, p in session_by_tday[teacher_id][old_day] if si != s_idx
            ]
        if new_day is not None:
            session_by_tday.setdefault(teacher_id, {}).setdefault(new_day, []).append(
                (s_idx, new_slot)
            )


def _build_conflict_indices(
    *, slot_by_session, classroom_by_session, sessions, slot_day_index
):
    """Build mutable conflict indices from the current assignment.
    Input: slot_by_session, classroom_by_session, sessions - current solution;
           slot_day_index - slot→day mapping
    Output: dict with keys teacher_day_slots, group_slot_set, classroom_slot_set,
            session_by_teacher_day
    """
    teacher_day_slots = {}
    group_slot_set = {}
    classroom_slot_set = {}
    session_by_teacher_day = {}

    for s_idx, session in enumerate(sessions):
        assigned = slot_by_session[s_idx]
        day_idx = slot_day_index.get(assigned)

        teacher_id = session.get("teacher_id")
        group = session.get("group")
        group_id = getattr(group, "id", None)
        classroom = classroom_by_session[s_idx]
        classroom_id = getattr(classroom, "id", None)

        if teacher_id is not None and day_idx is not None:
            teacher_day_slots.setdefault(teacher_id, {}).setdefault(day_idx, set()).add(
                assigned
            )
            session_by_teacher_day.setdefault(teacher_id, {}).setdefault(
                day_idx, []
            ).append((s_idx, assigned))

        if group_id is not None:
            group_slot_set.setdefault(group_id, set()).add(assigned)

        if classroom_id is not None:
            classroom_slot_set.setdefault(classroom_id, set()).add(assigned)

    return {
        "teacher_day_slots": teacher_day_slots,
        "group_slot_set": group_slot_set,
        "classroom_slot_set": classroom_slot_set,
        "session_by_teacher_day": session_by_teacher_day,
    }


def _build_slots_by_day(*, slots, slot_day_index):
    """Group slot indices by day index, sorted by start time.
    Input: slots - list of slot dicts; slot_day_index - slot→day mapping
    Output: dict {day_idx: [slot_idx, ...]} sorted by slot start time within each day
    """
    slots_by_day = {}
    for slot_idx, day_idx in slot_day_index.items():
        slots_by_day.setdefault(day_idx, []).append(slot_idx)
    for day_idx in slots_by_day:
        slots_by_day[day_idx].sort(key=lambda idx: slot_time_bounds(slot=slots[idx])[0])
    return slots_by_day
