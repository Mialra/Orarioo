"""Greedy post-processing to compact teacher schedules after CP-SAT.

Runs hill-climbing moves that shift individual sessions into intraday gap
slots, reducing teacher gaps without violating hard constraints.
"""

import time

from django.utils import timezone

from schedule.algorithm.slots import (
    build_slot_day_index,
    build_stage_allowed_slot_index,
    session_stage_code,
    slot_time_bounds,
)
from schedule.constants import AUTO_GENERATED_OBSERVATION


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
                teacher_day = teacher_day_slots[teacher_id].get(day_idx, set())
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


def _build_tc_occupation(*, sessions, slot_by_session, slots, teachers, slot_day_index):
    """Build teacher occupation index from CP-SAT assignments using slot indices.
    Input: sessions - session dicts; slot_by_session - CP-SAT result;
           slots - slot dicts; teachers - Teacher instances;
           slot_day_index - {slot_idx: day_idx} mapping
    Output: (teacher_assigned_slots, teacher_session_count, teacher_max_hours, teacher_day_slots)
    """
    teacher_assigned_slots = {}
    teacher_session_count = {t.id: 0 for t in teachers}
    teacher_day_slots = {}

    for session_idx, slot_idx in enumerate(slot_by_session):
        teacher = sessions[session_idx].get("teacher")
        if teacher is None:
            continue
        teacher_assigned_slots.setdefault(teacher.id, set()).add(slot_idx)
        teacher_session_count[teacher.id] += 1
        day_idx = slot_day_index.get(slot_idx)
        if day_idx is not None:
            teacher_day_slots.setdefault(teacher.id, {}).setdefault(day_idx, []).append(
                slot_idx
            )

    for tid in teacher_day_slots:
        for day_idx in teacher_day_slots[tid]:
            teacher_day_slots[tid][day_idx].sort(key=lambda si: slots[si]["start"])

    teacher_max_hours = {t.id: t.max_weekly_hours for t in teachers}
    return (
        teacher_assigned_slots,
        teacher_session_count,
        teacher_max_hours,
        teacher_day_slots,
    )


def _tc_slot_groups(slots):
    """Group non-recess slot indices by their (start, end) window, sorted chronologically.
    Input: slots - list of slot dicts
    Output: sorted list of ((start, end), set_of_slot_indices) pairs
    """
    from collections import defaultdict

    groups = defaultdict(set)
    for idx, slot in enumerate(slots):
        if slot.get("is_recess"):
            continue
        groups[(slot["start"], slot["end"])].add(idx)
    return sorted(groups.items(), key=lambda kv: kv[0][0])


def _pick_tc_teacher_gap_aware(
    *,
    teachers,
    teacher_assigned_slots,
    tc_assigned_slots,
    teacher_day_slots,
    teacher_session_count,
    teacher_max_hours,
    window_slot_set,
    start_time,
    end_time,
    slots,
    slot_day_index,
):
    """Return the best eligible teacher for a TC window, or None.

    Eligibility: no slot-index overlap with regular or TC sessions, and below max_weekly_hours.
    Priority: teachers whose schedule has a gap at this window (sessions before AND after on the
    same day) — assigned TC fills the hole rather than creating isolated free time.
    Fallback: least-busy eligible teacher when no gap-filling candidates exist.
    Input: teachers - ordered Teacher list; teacher_assigned_slots - {id: set of slot indices};
           tc_assigned_slots - {id: set of TC slot indices}; teacher_day_slots - gap index;
           teacher_session_count, teacher_max_hours - capacity data;
           window_slot_set - frozenset of slot indices for this window;
           start_time, end_time - window datetime bounds; slots, slot_day_index - slot data
    Output: Teacher instance or None
    """
    eligible = []
    gap_filling = []

    for t in teachers:
        busy = teacher_assigned_slots.get(t.id, set()) | tc_assigned_slots.get(
            t.id, set()
        )
        if busy & window_slot_set:
            continue

        max_h = teacher_max_hours.get(t.id)
        if max_h is not None and teacher_session_count.get(t.id, 0) >= max_h:
            continue

        eligible.append(t)

        for slot_idx in window_slot_set:
            day_idx = slot_day_index.get(slot_idx)
            if day_idx is None:
                continue
            day_slots = teacher_day_slots.get(t.id, {}).get(day_idx, [])
            has_before = any(slots[s]["end"] <= start_time for s in day_slots)
            has_after = any(slots[s]["start"] >= end_time for s in day_slots)
            if has_before and has_after:
                gap_filling.append(t)
                break

    if not eligible:
        return None
    pool = gap_filling if gap_filling else eligible
    return min(pool, key=lambda t: teacher_session_count.get(t.id, 0))


def fill_tc_sessions(
    *, sessions, slot_by_session, slots, teachers, tc_subject, team, actor_email
):
    """Greedy TC fill: one pass over all non-recess time windows in chronological order.

    For each window, assigns a free teacher as TC.  Gap-filling teachers (those with
    sessions before AND after the window on the same day) are preferred to reduce
    fragmented free time.  Eligibility: no slot-index overlap with regular or already-
    assigned TC sessions, and within max_weekly_hours.  Skips windows with no eligible
    teacher.
    Input: sessions - session dicts from CP-SAT; slot_by_session - CP-SAT result;
           slots - slot dicts; teachers - Teacher instances;
           tc_subject - Subject with type=TC; team, actor_email - Schedule fields
    Output: list of unsaved Schedule instances
    """
    from schedule.models import Schedule

    slot_day_index = build_slot_day_index(slots=slots)
    (
        teacher_assigned_slots,
        teacher_session_count,
        teacher_max_hours,
        teacher_day_slots,
    ) = _build_tc_occupation(
        sessions=sessions,
        slot_by_session=slot_by_session,
        slots=slots,
        teachers=teachers,
        slot_day_index=slot_day_index,
    )

    tc_assigned_slots = {}
    timestamp = timezone.now()
    tc_entries = []

    for (start_time, end_time), window_slot_indices in _tc_slot_groups(slots):
        window_slot_set = frozenset(window_slot_indices)
        free_teacher = _pick_tc_teacher_gap_aware(
            teachers=teachers,
            teacher_assigned_slots=teacher_assigned_slots,
            tc_assigned_slots=tc_assigned_slots,
            teacher_day_slots=teacher_day_slots,
            teacher_session_count=teacher_session_count,
            teacher_max_hours=teacher_max_hours,
            window_slot_set=window_slot_set,
            start_time=start_time,
            end_time=end_time,
            slots=slots,
            slot_day_index=slot_day_index,
        )
        if free_teacher is None:
            continue

        tc_entries.append(
            Schedule(
                name=f"Auto TC {start_time:%Y-%m-%d %H:%M}",
                start_time=start_time,
                end_time=end_time,
                observations=AUTO_GENERATED_OBSERVATION,
                team=team,
                teacher=free_teacher,
                classroom=None,
                group=None,
                subject=tc_subject,
                created_by=actor_email,
                updated_by=actor_email,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )

        tc_assigned_slots.setdefault(free_teacher.id, set()).update(window_slot_set)
        teacher_session_count[free_teacher.id] += 1
        for slot_idx in window_slot_set:
            day_idx = slot_day_index.get(slot_idx)
            if day_idx is not None:
                teacher_day_slots.setdefault(free_teacher.id, {}).setdefault(
                    day_idx, []
                ).append(slot_idx)
                teacher_day_slots[free_teacher.id][day_idx].sort(
                    key=lambda si: slots[si]["start"]
                )

    return tc_entries
