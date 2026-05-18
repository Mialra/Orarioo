"""Structured infeasibility diagnostics for schedule generation."""

from __future__ import annotations

from collections import defaultdict

from common.errors.exceptions import NON_FIELD_ERRORS_KEY
from common.stages import EducationalStage, canonical_group_stage
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import (
    build_slot_preference_index,
    build_stage_allowed_slot_index,
    session_stage_code,
)
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState

CONFIGURATION_RANK = 10
CAPACITY_RANK = 20
AVAILABILITY_RANK = 30
BOTTLENECK_RANK = 40
FALLBACK_RANK = 90


def build_diagnostic(
    code,
    message,
    *,
    context=None,
    suggestions=None,
    severity="error",
    scope="schedule",
    entity_ids=None,
    rank=FALLBACK_RANK,
):
    """Return a structured diagnostic entry consumable by the API and frontend."""
    entry = {
        "code": str(code or "SCHEDULE_INFEASIBLE"),
        "message": str(message or ""),
        "context": dict(context or {}),
        "severity": severity,
        "scope": scope,
        "rank": int(rank),
    }
    if suggestions:
        entry["suggestions"] = list(suggestions)
    if entity_ids:
        entry["entity_ids"] = dict(entity_ids)
    return entry


def raise_schedule_generation_diagnostics(
    *,
    diagnostics,
    detail,
    code="SCHEDULE_INFEASIBLE",
    context=None,
    suggestions=None,
):
    """Raise a ScheduleGenerationError that exposes all diagnostics at once."""
    ordered = sort_diagnostics(diagnostics)
    merged_context = dict(context or {})
    merged_context["diagnostics"] = ordered

    merged_suggestions = list(suggestions or [])
    for item in ordered:
        for suggestion in item.get("suggestions", []):
            if suggestion not in merged_suggestions:
                merged_suggestions.append(suggestion)

    raise ScheduleGenerationError(
        detail,
        code=code,
        context=merged_context,
        suggestions=merged_suggestions,
        errors={NON_FIELD_ERRORS_KEY: ordered},
    )


def sort_diagnostics(diagnostics):
    """Sort diagnostics so the most actionable causes appear first."""
    return sorted(
        list(diagnostics or []),
        key=lambda item: (
            int(item.get("rank", FALLBACK_RANK)),
            str(item.get("code", "")),
            str(item.get("message", "")),
        ),
    )


def analyze_schedule_infeasibility(
    *,
    sessions,
    slots,
    classrooms,
    generation_options=None,
    fixed_assignments=None,
    compatible_classrooms_by_session=None,
    solver_status=None,
    solver_context=None,
):
    """Collect actionable diagnostics for an infeasible generation attempt."""
    diagnostics = collect_generation_diagnostics(
        sessions=sessions,
        slots=slots,
        classrooms=classrooms,
        generation_options=generation_options,
        fixed_assignments=fixed_assignments,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
    )
    if diagnostics:
        return diagnostics
    return [
        _build_fallback_solver_diagnostic(
            solver_status=solver_status,
            solver_context=solver_context or {},
        )
    ]


def collect_generation_diagnostics(
    *,
    sessions,
    slots,
    classrooms,
    generation_options=None,
    fixed_assignments=None,
    compatible_classrooms_by_session=None,
    subjects=None,
    teachers=None,
):
    """Collect structured diagnostics before or after attempting the solve."""
    diagnostics = []
    if subjects is not None or teachers is not None:
        diagnostics.extend(
            _collect_configuration_diagnostics(
                subjects=subjects or [],
                teachers=teachers or [],
                classrooms=classrooms or [],
            )
        )

    if not sessions or not slots:
        return sort_diagnostics(diagnostics)

    compatible_by_session = (
        compatible_classrooms_by_session
        if compatible_classrooms_by_session is not None
        else _build_compatible_classrooms_by_session(
            sessions=sessions,
            classrooms=classrooms or [],
        )
    )

    diagnostics.extend(
        _collect_classroom_compatibility_diagnostics(
            sessions=sessions,
            compatible_classrooms_by_session=compatible_by_session,
        )
    )
    diagnostics.extend(
        _collect_capacity_diagnostics(
            sessions=sessions,
            slots=slots,
            generation_options=generation_options or {},
        )
    )

    feasible_slots_by_session = _build_feasible_slots_by_session(
        sessions=sessions,
        slots=slots,
        fixed_assignments=fixed_assignments or {},
    )
    diagnostics.extend(
        _collect_availability_diagnostics(
            sessions=sessions,
            slots=slots,
            feasible_slots_by_session=feasible_slots_by_session,
        )
    )
    diagnostics.extend(
        _collect_bottleneck_diagnostics(
            sessions=sessions,
            slots=slots,
            feasible_slots_by_session=feasible_slots_by_session,
            compatible_classrooms_by_session=compatible_by_session,
            generation_options=generation_options or {},
        )
    )
    return _dedupe_diagnostics(sort_diagnostics(diagnostics))


def _collect_configuration_diagnostics(*, subjects, teachers, classrooms):
    diagnostics = []
    if not teachers:
        diagnostics.append(
            build_diagnostic(
                "MISSING_TEACHERS",
                "At least one teacher is required before generating a schedule.",
                suggestions=[
                    "Crea al menos un profesor antes de generar el horario.",
                ],
                rank=CONFIGURATION_RANK,
            )
        )
    if subjects == []:
        diagnostics.append(
            build_diagnostic(
                "MISSING_SUBJECTS",
                "At least one subject is required before generating a schedule.",
                suggestions=[
                    "Crea al menos una asignatura con horas semanales antes de generar el horario.",
                ],
                rank=CONFIGURATION_RANK,
            )
        )
    for subject in subjects:
        if getattr(subject, "teacher_id", None) is None:
            diagnostics.append(
                build_diagnostic(
                    "SUBJECT_WITHOUT_TEACHER",
                    f"Subject '{getattr(subject, 'name', 'Unknown subject')}' has no teacher assigned.",
                    context={
                        "subject_id": getattr(subject, "id", None),
                        "subject_name": getattr(subject, "name", ""),
                    },
                    suggestions=[
                        "Asigna un profesor a la asignatura antes de generar el horario.",
                    ],
                    scope="subject",
                    entity_ids={"subject_id": getattr(subject, "id", None)},
                    rank=CONFIGURATION_RANK,
                )
            )
        group = getattr(subject, "group", None)
        if getattr(subject, "group_id", None) is None:
            diagnostics.append(
                build_diagnostic(
                    "SUBJECT_WITHOUT_GROUP",
                    f"Subject '{getattr(subject, 'name', 'Unknown subject')}' has no group assigned.",
                    context={
                        "subject_id": getattr(subject, "id", None),
                        "subject_name": getattr(subject, "name", ""),
                    },
                    suggestions=[
                        "Asigna un curso a la asignatura antes de generar el horario.",
                    ],
                    scope="subject",
                    entity_ids={"subject_id": getattr(subject, "id", None)},
                    rank=CONFIGURATION_RANK,
                )
            )
        elif canonical_group_stage(getattr(group, "stage", None), None) not in {
            EducationalStage.PRESCHOOL,
            EducationalStage.PRIMARY,
            EducationalStage.SECONDARY,
            EducationalStage.ALEVELS,
        }:
            diagnostics.append(
                build_diagnostic(
                    "GROUP_WITHOUT_STAGE",
                    f"Group '{getattr(group, 'name', 'Unknown group')}' has an invalid educational stage.",
                    context={
                        "group_id": getattr(group, "id", None),
                        "group_name": getattr(group, "name", ""),
                        "stage": getattr(group, "stage", ""),
                    },
                    suggestions=[
                        "Revisa la etapa educativa del grupo.",
                    ],
                    scope="group",
                    entity_ids={"group_id": getattr(group, "id", None)},
                    rank=CONFIGURATION_RANK,
                )
            )

    return diagnostics


def _collect_classroom_compatibility_diagnostics(
    *, sessions, compatible_classrooms_by_session
):
    diagnostics = []
    for session_idx, session in enumerate(sessions):
        compatible = compatible_classrooms_by_session.get(session_idx, [])
        if compatible:
            continue
        subject = session.get("subject")
        group = session.get("group")
        diagnostics.append(
            build_diagnostic(
                "NO_COMPATIBLE_CLASSROOM",
                _classroom_compatibility_error(session=session),
                context={
                    "session_index": session_idx,
                    "subject_id": getattr(subject, "id", None),
                    "subject": getattr(subject, "name", ""),
                    "group_id": getattr(group, "id", None),
                    "group": getattr(group, "name", ""),
                    "allowed_classroom_ids": sorted(
                        session.get("allowed_classroom_ids") or []
                    ),
                },
                suggestions=[
                    "Asigna al menos un aula compatible a la asignatura.",
                    "Crea un aula compartida si la asignatura necesita un aula especializada.",
                ],
                scope="subject",
                entity_ids={
                    "subject_id": getattr(subject, "id", None),
                    "group_id": getattr(group, "id", None),
                },
                rank=CONFIGURATION_RANK,
            )
        )
    return diagnostics


def _check_group_capacities(sessions_by_group, sessions, slots):
    diagnostics = []
    slot_count = len(slots)
    for session_indices in sessions_by_group.values():
        group = sessions[session_indices[0]].get("group")
        assigned = len(session_indices)
        weekly_limit = _group_weekly_limit(group)
        daily_limit = _group_daily_limit(group)
        if assigned > slot_count:
            diagnostics.append(
                build_diagnostic(
                    "GROUP_SLOT_CAPACITY_EXCEEDED",
                    f"Group '{group.name}' needs {assigned} sessions but only {slot_count} slots exist in the current timetable.",
                    context={
                        "group_id": group.id,
                        "group_name": group.name,
                        "required_sessions": assigned,
                        "available_slots": slot_count,
                    },
                    suggestions=[
                        "Reduce las horas semanales del grupo.",
                        "Revisa si las restricciones horarias están eliminando demasiados huecos.",
                    ],
                    scope="group",
                    entity_ids={"group_id": group.id},
                    rank=CAPACITY_RANK,
                )
            )
        if assigned > weekly_limit:
            diagnostics.append(
                build_diagnostic(
                    "GROUP_WEEKLY_CAPACITY_EXCEEDED",
                    f"Group '{group.name}' exceeds its weekly capacity: {assigned} sessions assigned, {weekly_limit} allowed.",
                    context={
                        "group_id": group.id,
                        "group_name": group.name,
                        "assigned_sessions": assigned,
                        "capacity": weekly_limit,
                    },
                    suggestions=[
                        "Reduce las horas semanales asignadas a este curso.",
                    ],
                    scope="group",
                    entity_ids={"group_id": group.id},
                    rank=CAPACITY_RANK,
                )
            )
        if assigned > daily_limit * 5:
            diagnostics.append(
                build_diagnostic(
                    "GROUP_DAILY_CAPACITY_EXCEEDED",
                    f"Group '{group.name}' cannot fit {assigned} sessions without exceeding its daily limit of {daily_limit}.",
                    context={
                        "group_id": group.id,
                        "group_name": group.name,
                        "assigned_sessions": assigned,
                        "daily_capacity": daily_limit,
                    },
                    suggestions=[
                        "Reduce las horas semanales del grupo o relaja restricciones que concentran demasiadas sesiones en pocos días.",
                    ],
                    scope="group",
                    entity_ids={"group_id": group.id},
                    rank=CAPACITY_RANK + 1,
                )
            )
    return diagnostics


def _check_teacher_capacities(sessions_by_teacher, sessions):
    diagnostics = []
    for session_indices in sessions_by_teacher.values():
        teacher = sessions[session_indices[0]].get("teacher")
        assigned = len(session_indices)
        max_weekly_hours = (getattr(teacher, "max_weekly_hours", 0) or 0) + (
            getattr(teacher, "max_weekly_minutes", 0) or 0
        ) / 60.0
        if assigned > max_weekly_hours:
            diagnostics.append(
                build_diagnostic(
                    "TEACHER_WEEKLY_CAPACITY_EXCEEDED",
                    f"Teacher '{teacher.name}' exceeds the weekly workload limit: {assigned} sessions assigned, {max_weekly_hours} allowed.",
                    context={
                        "teacher_id": teacher.id,
                        "teacher_name": teacher.name,
                        "assigned_sessions": assigned,
                        "capacity": max_weekly_hours,
                    },
                    suggestions=[
                        "Aumenta el máximo semanal del profesor o reparte parte de la carga con otro profesor.",
                    ],
                    scope="teacher",
                    entity_ids={"teacher_id": teacher.id},
                    rank=CAPACITY_RANK,
                )
            )
    return diagnostics


def _collect_capacity_diagnostics(*, sessions, slots, generation_options):
    sessions_by_group = defaultdict(list)
    sessions_by_teacher = defaultdict(list)

    for session_idx, session in enumerate(sessions):
        group = session.get("group")
        if getattr(group, "id", None) is not None:
            sessions_by_group[group.id].append(session_idx)
        teacher = session.get("teacher")
        if getattr(teacher, "id", None) is not None:
            sessions_by_teacher[teacher.id].append(session_idx)

    diagnostics = []
    diagnostics.extend(_check_group_capacities(sessions_by_group, sessions, slots))
    diagnostics.extend(_check_teacher_capacities(sessions_by_teacher, sessions))
    return diagnostics


def _collect_availability_diagnostics(*, sessions, slots, feasible_slots_by_session):
    diagnostics = []
    diagnostics.extend(
        _build_aggregate_availability_diagnostics(
            sessions=sessions,
            feasible_slots_by_session=feasible_slots_by_session,
            scope="subject",
        )
    )
    diagnostics.extend(
        _build_aggregate_availability_diagnostics(
            sessions=sessions,
            feasible_slots_by_session=feasible_slots_by_session,
            scope="teacher",
        )
    )
    diagnostics.extend(
        _build_aggregate_availability_diagnostics(
            sessions=sessions,
            feasible_slots_by_session=feasible_slots_by_session,
            scope="group",
        )
    )
    diagnostics.extend(
        _build_subject_teacher_mismatch_diagnostics(
            sessions=sessions,
            slots=slots,
            feasible_slots_by_session=feasible_slots_by_session,
        )
    )
    diagnostics.extend(
        _build_stage_window_diagnostics(
            sessions=sessions,
            slots=slots,
        )
    )
    return diagnostics


def _collect_bottleneck_diagnostics(
    *,
    sessions,
    slots,
    feasible_slots_by_session,
    compatible_classrooms_by_session,
    generation_options,
):
    diagnostics = []
    diagnostics.extend(
        _build_overlapped_demand_diagnostics(
            sessions=sessions,
            feasible_slots_by_session=feasible_slots_by_session,
            scope="teacher",
        )
    )
    diagnostics.extend(
        _build_overlapped_demand_diagnostics(
            sessions=sessions,
            feasible_slots_by_session=feasible_slots_by_session,
            scope="group",
        )
    )
    diagnostics.extend(
        _build_classroom_bottleneck_diagnostics(
            sessions=sessions,
            feasible_slots_by_session=feasible_slots_by_session,
            compatible_classrooms_by_session=compatible_classrooms_by_session,
        )
    )
    if generation_options.get("enable_no_intraday_gaps", True):
        diagnostics.extend(
            _build_no_gap_diagnostics(
                sessions=sessions,
                slots=slots,
                feasible_slots_by_session=feasible_slots_by_session,
            )
        )
    return diagnostics


def _build_aggregate_availability_diagnostics(
    *, sessions, feasible_slots_by_session, scope
):
    diagnostics = []
    grouped = defaultdict(list)

    for session_idx, session in enumerate(sessions):
        entity = _scope_entity(session=session, scope=scope)
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            continue
        grouped[entity_id].append(session_idx)

    for session_indices in grouped.values():
        entity = _scope_entity(session=sessions[session_indices[0]], scope=scope)
        entity_name = getattr(entity, "name", "") or "sin nombre"
        union_slots = set()
        for session_idx in session_indices:
            union_slots.update(feasible_slots_by_session.get(session_idx, set()))
        required_sessions = len(session_indices)
        available_slots = len(union_slots)
        if available_slots == 0:
            code = f"{scope.upper()}_NO_AVAILABLE_SLOTS"
            diagnostics.append(
                build_diagnostic(
                    code,
                    f"{scope.title()} '{entity_name}' has no available slots after applying the current constraints.",
                    context=_scope_context(
                        scope=scope,
                        entity=entity,
                        required_sessions=required_sessions,
                        available_slots=available_slots,
                    ),
                    suggestions=_availability_suggestions(scope=scope),
                    scope=scope,
                    entity_ids={f"{scope}_id": getattr(entity, "id", None)},
                    rank=AVAILABILITY_RANK,
                )
            )
        elif available_slots < required_sessions:
            code = f"{scope.upper()}_INSUFFICIENT_AVAILABLE_SLOTS"
            diagnostics.append(
                build_diagnostic(
                    code,
                    f"{scope.title()} '{entity_name}' needs {required_sessions} sessions but only has {available_slots} compatible slots.",
                    context=_scope_context(
                        scope=scope,
                        entity=entity,
                        required_sessions=required_sessions,
                        available_slots=available_slots,
                    ),
                    suggestions=_availability_suggestions(scope=scope),
                    scope=scope,
                    entity_ids={f"{scope}_id": getattr(entity, "id", None)},
                    rank=AVAILABILITY_RANK,
                )
            )
    return diagnostics


def _build_subject_teacher_mismatch_diagnostics(
    *, sessions, slots, feasible_slots_by_session
):
    diagnostics = []
    base_slots_by_session = _build_feasible_slots_by_session(
        sessions=sessions,
        slots=slots,
        fixed_assignments={},
        include_subject_preferences=False,
        include_teacher_preferences=False,
    )
    teacher_only_by_session = _build_feasible_slots_by_session(
        sessions=sessions,
        slots=slots,
        fixed_assignments={},
        include_subject_preferences=False,
        include_teacher_preferences=True,
    )
    subject_only_by_session = _build_feasible_slots_by_session(
        sessions=sessions,
        slots=slots,
        fixed_assignments={},
        include_subject_preferences=True,
        include_teacher_preferences=False,
    )

    subjects_by_id = defaultdict(list)
    for session_idx, session in enumerate(sessions):
        subject = session.get("subject")
        subject_id = getattr(subject, "id", None)
        if subject_id is not None:
            subjects_by_id[subject_id].append(session_idx)

    for session_indices in subjects_by_id.values():
        subject = sessions[session_indices[0]].get("subject")
        teacher = sessions[session_indices[0]].get("teacher")
        if getattr(subject, "id", None) is None or getattr(teacher, "id", None) is None:
            continue
        base_slots = set()
        teacher_slots = set()
        subject_slots = set()
        for session_idx in session_indices:
            base_slots.update(base_slots_by_session.get(session_idx, set()))
            teacher_slots.update(teacher_only_by_session.get(session_idx, set()))
            subject_slots.update(subject_only_by_session.get(session_idx, set()))
        overlap = len(feasible_slots_by_session.get(session_indices[0], set()))
        max_possible = min(len(teacher_slots), len(subject_slots), len(base_slots))
        if max_possible >= 3 and overlap <= 1:
            diagnostics.append(
                build_diagnostic(
                    "SUBJECT_TEACHER_AVAILABILITY_MISMATCH",
                    f"Subject '{subject.name}' and teacher '{teacher.name}' barely share compatible time slots.",
                    context={
                        "subject_id": subject.id,
                        "subject_name": subject.name,
                        "teacher_id": teacher.id,
                        "teacher_name": teacher.name,
                        "overlap_slots": overlap,
                        "subject_slots": len(subject_slots),
                        "teacher_slots": len(teacher_slots),
                    },
                    suggestions=[
                        "Amplía la disponibilidad del profesor o elimina indisponibilidades de la asignatura.",
                    ],
                    scope="subject",
                    entity_ids={
                        "subject_id": subject.id,
                        "teacher_id": teacher.id,
                    },
                    rank=BOTTLENECK_RANK,
                )
            )
    return diagnostics


def _build_stage_window_diagnostics(*, sessions, slots):
    diagnostics = []
    non_recess_slots_by_stage = defaultdict(set)
    for slot_idx, slot in enumerate(slots):
        if slot.get("is_recess"):
            continue
        non_recess_slots_by_stage[slot.get("stage")].add(slot_idx)

    grouped = defaultdict(list)
    for session_idx, session in enumerate(sessions):
        group = session.get("group")
        group_id = getattr(group, "id", None)
        if group_id is not None:
            grouped[group_id].append(session_idx)

    for session_indices in grouped.values():
        group = sessions[session_indices[0]].get("group")
        stage_code = session_stage_code(session=sessions[session_indices[0]])
        allowed_slots = len(non_recess_slots_by_stage.get(stage_code, set()))
        required_sessions = len(session_indices)
        if allowed_slots and allowed_slots < required_sessions:
            diagnostics.append(
                build_diagnostic(
                    "STAGE_SLOT_WINDOW_TOO_NARROW",
                    f"Group '{group.name}' belongs to a stage with only {allowed_slots} usable slots for {required_sessions} sessions.",
                    context={
                        "group_id": group.id,
                        "group_name": group.name,
                        "stage": stage_code,
                        "required_sessions": required_sessions,
                        "available_slots": allowed_slots,
                    },
                    suggestions=[
                        "Amplía la franja horaria configurada para la etapa o reduce las sesiones de ese curso.",
                    ],
                    scope="group",
                    entity_ids={"group_id": group.id},
                    rank=BOTTLENECK_RANK,
                )
            )
    return diagnostics


def _build_overlapped_demand_diagnostics(*, sessions, feasible_slots_by_session, scope):
    diagnostics = []
    grouped = defaultdict(list)

    for session_idx, session in enumerate(sessions):
        entity = _scope_entity(session=session, scope=scope)
        entity_id = getattr(entity, "id", None)
        if entity_id is not None:
            grouped[entity_id].append(session_idx)

    for session_indices in grouped.values():
        subjects = {
            getattr(sessions[session_idx].get("subject"), "name", "")
            for session_idx in session_indices
        }
        if len(subjects) < 2:
            continue
        union_slots = set()
        for session_idx in session_indices:
            union_slots.update(feasible_slots_by_session.get(session_idx, set()))
        required_sessions = len(session_indices)
        if union_slots and len(union_slots) <= required_sessions + 1:
            entity = _scope_entity(session=sessions[session_indices[0]], scope=scope)
            entity_name = getattr(entity, "name", "") or "sin nombre"
            diagnostics.append(
                build_diagnostic(
                    f"{scope.upper()}_OVERLAPPED_DEMAND",
                    f"{scope.title()} '{entity_name}' has several subjects competing for a very small set of slots.",
                    context={
                        f"{scope}_id": getattr(entity, "id", None),
                        f"{scope}_name": entity_name,
                        "required_sessions": required_sessions,
                        "available_slots": len(union_slots),
                        "subject_names": sorted(name for name in subjects if name),
                    },
                    suggestions=[
                        "Reduce indisponibilidades o redistribuye parte de la carga a otros recursos.",
                    ],
                    scope=scope,
                    entity_ids={f"{scope}_id": getattr(entity, "id", None)},
                    rank=BOTTLENECK_RANK,
                )
            )
    return diagnostics


def _build_classroom_bottleneck_diagnostics(
    *, sessions, feasible_slots_by_session, compatible_classrooms_by_session
):
    diagnostics = []
    grouped = defaultdict(list)

    for session_idx, compatible_classrooms in compatible_classrooms_by_session.items():
        compatible_ids = sorted(
            getattr(item, "id", None) for item in compatible_classrooms
        )
        if not compatible_ids:
            continue
        grouped[tuple(compatible_ids)].append(session_idx)

    for classroom_ids, session_indices in grouped.items():
        if len(classroom_ids) > 2 or len(session_indices) < 2:
            continue
        union_slots = set()
        for session_idx in session_indices:
            union_slots.update(feasible_slots_by_session.get(session_idx, set()))
        max_capacity = len(union_slots) * len(classroom_ids)
        if max_capacity >= len(session_indices):
            continue
        subject_names = sorted(
            {
                getattr(sessions[session_idx].get("subject"), "name", "")
                for session_idx in session_indices
            }
        )
        diagnostics.append(
            build_diagnostic(
                "CLASSROOM_BOTTLENECK",
                "Several sessions depend on too few compatible classrooms to fit into the available timetable.",
                context={
                    "classroom_ids": list(classroom_ids),
                    "required_sessions": len(session_indices),
                    "available_slots": len(union_slots),
                    "compatible_classroom_count": len(classroom_ids),
                    "subject_names": [name for name in subject_names if name],
                },
                suggestions=[
                    "Añade más aulas compatibles o amplía la disponibilidad de las asignaturas afectadas.",
                ],
                scope="classroom",
                entity_ids={"classroom_ids": list(classroom_ids)},
                rank=BOTTLENECK_RANK,
            )
        )
    return diagnostics


def _build_no_gap_diagnostics(*, sessions, slots, feasible_slots_by_session):
    diagnostics = []
    slots_by_day = defaultdict(list)
    for slot_idx, slot in enumerate(slots):
        if slot.get("is_recess"):
            continue
        slots_by_day[slot["start"].date()].append(slot_idx)

    grouped = defaultdict(list)
    for session_idx, session in enumerate(sessions):
        group = session.get("group")
        if getattr(group, "id", None) is not None:
            grouped[group.id].append(session_idx)

    for session_indices in grouped.values():
        group = sessions[session_indices[0]].get("group")
        possible_days = set()
        for session_idx in session_indices:
            for slot_idx in feasible_slots_by_session.get(session_idx, set()):
                possible_days.add(slots[slot_idx]["start"].date())
        if possible_days and len(possible_days) == 1 and len(session_indices) >= 2:
            diagnostics.append(
                build_diagnostic(
                    "NO_GAP_CONSTRAINT_TOO_STRICT",
                    f"Group '{group.name}' can only place its sessions on a single day, which makes the no-gap rule very restrictive.",
                    context={
                        "group_id": group.id,
                        "group_name": group.name,
                        "required_sessions": len(session_indices),
                        "available_days": len(possible_days),
                    },
                    suggestions=[
                        "Amplía huecos en otros días o desactiva temporalmente la restricción de no huecos intermedios.",
                    ],
                    scope="group",
                    entity_ids={"group_id": group.id},
                    rank=BOTTLENECK_RANK,
                )
            )
    return diagnostics


def _build_fallback_solver_diagnostic(*, solver_status, solver_context):
    status_name = str(
        solver_status or solver_context.get("solver_status") or ""
    ).upper()
    timeout_seconds = solver_context.get("timeout_seconds")
    if status_name == "UNKNOWN" and timeout_seconds:
        return build_diagnostic(
            "SCHEDULE_SOLVER_TIMEOUT",
            "The solver could not finish within the configured time limit.",
            context=dict(solver_context),
            suggestions=[
                "Aumenta el tiempo máximo de generación o reduce restricciones muy duras.",
            ],
            rank=FALLBACK_RANK,
        )
    if status_name == "MODEL_INVALID":
        return build_diagnostic(
            "SCHEDULE_MODEL_INVALID",
            "The schedule model is invalid with the current inputs.",
            context=dict(solver_context),
            suggestions=[
                "Revisa la configuración del horario y los datos de entrada.",
            ],
            rank=FALLBACK_RANK,
        )
    return build_diagnostic(
        "SCHEDULE_INFEASIBLE",
        "The schedule cannot be generated with the current hard constraints.",
        context=dict(solver_context),
        suggestions=[
            "Revisa las indisponibilidades de profesores y asignaturas.",
            "Añade más aulas compatibles si hay materias que dependen de espacios concretos.",
        ],
        rank=FALLBACK_RANK,
    )


def _build_feasible_slots_by_session(
    *,
    sessions,
    slots,
    fixed_assignments,
    include_subject_preferences=True,
    include_teacher_preferences=True,
):
    allowed_slots_by_stage = build_stage_allowed_slot_index(slots=slots)
    slot_preference_by_idx = build_slot_preference_index(slots=slots)
    feasible_slots_by_session = {}

    for session_idx, session in enumerate(sessions):
        stage_code = session_stage_code(session=session)
        slot_indices = {
            slot_idx
            for slot_idx in allowed_slots_by_stage.get(stage_code, set())
            if not slots[slot_idx].get("is_recess")
        }
        fixed_slot_idx = fixed_assignments.get(session_idx)
        if fixed_slot_idx is not None:
            slot_indices &= {fixed_slot_idx}

        if include_subject_preferences:
            slot_indices = {
                slot_idx
                for slot_idx in slot_indices
                if _subject_state(
                    session=session,
                    slot_idx=slot_idx,
                    slots=slots,
                    slot_preference_by_idx=slot_preference_by_idx,
                )
                != SubjectTimePreferenceState.UNAVAILABLE
            }
        if include_teacher_preferences:
            slot_indices = {
                slot_idx
                for slot_idx in slot_indices
                if _teacher_state(
                    session=session,
                    slot_idx=slot_idx,
                    slots=slots,
                    slot_preference_by_idx=slot_preference_by_idx,
                )
                != TeacherTimePreferenceState.UNAVAILABLE
            }

        feasible_slots_by_session[session_idx] = slot_indices
    return feasible_slots_by_session


def _build_compatible_classrooms_by_session(*, sessions, classrooms):
    index = {}
    for session_idx, session in enumerate(sessions):
        allowed_classroom_ids = session.get("allowed_classroom_ids")
        compatible = [
            classroom
            for classroom in classrooms
            if _is_classroom_compatible(session=session, classroom=classroom)
        ]
        if not allowed_classroom_ids:
            default_classroom = _find_group_default_classroom(
                session=session,
                classrooms=classrooms,
            )
            if default_classroom is not None:
                compatible = [default_classroom]
        index[session_idx] = compatible
    return index


def _scope_entity(*, session, scope):
    if scope == "teacher":
        return session.get("teacher")
    if scope == "group":
        return session.get("group")
    return session.get("subject")


def _scope_context(*, scope, entity, required_sessions, available_slots):
    return {
        f"{scope}_id": getattr(entity, "id", None),
        f"{scope}_name": getattr(entity, "name", ""),
        "required_sessions": required_sessions,
        "available_slots": available_slots,
    }


def _availability_suggestions(*, scope):
    if scope == "teacher":
        return [
            "Amplía la disponibilidad del profesor o reduce parte de su carga.",
        ]
    if scope == "group":
        return [
            "Reduce horas del curso o libera más huecos compatibles para ese grupo.",
        ]
    return [
        "Libera más franjas horarias para la asignatura o reduce sus horas semanales.",
    ]


def _subject_state(*, session, slot_idx, slots, slot_preference_by_idx):
    subject = session.get("subject")
    if subject is None:
        return SubjectTimePreferenceState.AVAILABLE
    slot_key = slot_preference_by_idx.get(slot_idx)
    preferences = getattr(subject, "time_preferences", None) or {}
    state = preferences.get(slot_key)
    if state in SubjectTimePreferenceState.values:
        return state
    return SubjectTimePreferenceState.AVAILABLE


def _teacher_state(*, session, slot_idx, slots, slot_preference_by_idx):
    teacher = session.get("teacher")
    if teacher is None:
        return TeacherTimePreferenceState.AVAILABLE
    slot_key = slot_preference_by_idx.get(slot_idx)
    preferences = getattr(teacher, "time_preferences", None) or {}
    state = preferences.get(slot_key)
    if state in TeacherTimePreferenceState.values:
        return state
    return TeacherTimePreferenceState.AVAILABLE


def _group_weekly_limit(group):
    if canonical_group_stage(getattr(group, "stage", None)) in {
        EducationalStage.PRESCHOOL,
        EducationalStage.PRIMARY,
    }:
        return 25
    return 30


def _group_daily_limit(group):
    if canonical_group_stage(getattr(group, "stage", None)) in {
        EducationalStage.PRESCHOOL,
        EducationalStage.PRIMARY,
    }:
        return 5
    return 6


def _is_classroom_compatible(*, session, classroom):
    allowed_ids = session.get("allowed_classroom_ids")
    if not allowed_ids:
        return True
    return getattr(classroom, "id", None) in allowed_ids


def _find_group_default_classroom(*, session, classrooms):
    group = session.get("group")
    group_name = getattr(group, "name", "").strip()
    if not group_name:
        return None
    expected_name = f"Aula {group_name}".casefold()
    for classroom in classrooms:
        if getattr(classroom, "name", "").strip().casefold() == expected_name:
            return classroom
    return None


def _classroom_compatibility_error(*, session):
    subject = session.get("subject")
    subject_name = getattr(subject, "name", "Unknown subject")
    return (
        "Could not assign a classroom to at least one generated session. "
        "No available classroom matches subject '{subject_name}'."
    ).format(subject_name=subject_name)


def _dedupe_diagnostics(diagnostics):
    seen = set()
    unique = []
    for item in diagnostics:
        context = item.get("context") or {}
        signature = (
            item.get("code"),
            tuple(sorted((str(key), str(value)) for key, value in context.items())),
        )
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(item)
    return unique
