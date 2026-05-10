"""Schedule generator and replanner using the CP-SAT constraint solver.

BasicScheduleGenerator creates a full weekly timetable from scratch.
ScheduleReplanner replans an existing timetable after a manual session move.
"""

import random

from django.db import transaction
from django.utils import timezone

from auditableEntity.audit import create_audit_entry, suppress_audit_events
from auditableEntity.models import AuditActionType
from classroom.models import Classroom
from group.models import Group
from schedule.algorithm.assignment import solve_session_assignment
from schedule.algorithm.diagnostics import (
    BOTTLENECK_RANK,
    collect_generation_diagnostics,
    raise_schedule_generation_diagnostics,
)
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import (
    build_weekly_slots,
    parse_schedule_config_to_slot_windows,
    session_stage_code,
    slot_instance_key,
)
from schedule.constants import AUTO_GENERATED_OBSERVATION
from schedule.models import Schedule
from subject.models import Subject
from teacher.models import Teacher

# ---------------------------------------------------------------------------
# Module-level helpers shared by both generator classes
# ---------------------------------------------------------------------------


def _get_or_create_classroom(actor_email: str, team):
    """Return the first classroom for the team, creating a default one if none exist.
    Input: actor_email - email used as created_by/updated_by on creation;
           team - Team model instance
    Output: Classroom instance
    """
    classroom = Classroom.objects.filter(team=team).order_by("id").first()
    if classroom is not None:
        return classroom
    return Classroom.objects.create(
        name="Auto Classroom",
        team=team,
        created_by=actor_email,
        updated_by=actor_email,
    )


def _get_or_create_group(actor_email: str, team):
    """Return the first group for the team, creating a default PRIMARY group if none exist.
    Input: actor_email - email used as created_by/updated_by on creation;
           team - Team model instance
    Output: Group instance
    """
    group = Group.objects.filter(team=team).order_by("id").first()
    if group is not None:
        return group
    return Group.objects.create(
        name="Auto Group",
        stage="PRIMARY",
        team=team,
        created_by=actor_email,
        updated_by=actor_email,
    )


def _build_classroom_pool(*, fallback_classroom, team):
    """Return all classrooms for the team, falling back to a single default one.
    Input: fallback_classroom - Classroom instance to use when none exist in DB;
           team - Team model instance
    Output: list of Classroom instances
    """
    classrooms = list(Classroom.objects.filter(team=team).order_by("id"))
    if not classrooms:
        return [fallback_classroom]
    return classrooms


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class BasicScheduleGenerator:
    """Generates a complete weekly timetable from scratch using CP-SAT."""

    @classmethod
    @transaction.atomic
    def generate(
        cls,
        *,
        actor_email: str,
        user,
        team,
        random_seed: int | None = None,
        generation_options=None,
    ):
        """Generate and persist a full weekly schedule for the given team.
        Input: actor_email - email of the user triggering generation;
               user - Django User instance (owner of the generated schedules);
               team - Team model instance;
               random_seed - optional integer seed for reproducibility;
               generation_options - dict with generation parameters
        Output: list of created Schedule instances; empty list if no sessions to schedule
        """
        generation_options = generation_options or {}
        cls._clear_previous_generated_schedules(
            actor_email=actor_email,
            user=user,
            team=team,
        )

        teachers = list(Teacher.objects.filter(team=team).order_by("id"))
        teacher = teachers[0] if teachers else None
        subjects = list(
            Subject.objects.filter(team=team)
            .select_related("teacher", "group", "mandatory_classroom")
            .order_by("id")
        )
        fallback_classroom = _get_or_create_classroom(actor_email, team)
        classrooms = _build_classroom_pool(
            fallback_classroom=fallback_classroom,
            team=team,
        )
        custom_windows = parse_schedule_config_to_slot_windows(
            getattr(team, "schedule_config", None)
        )
        slots = build_weekly_slots(stage_slot_windows=custom_windows)

        if teacher is None or not subjects:
            diagnostics = collect_generation_diagnostics(
                subjects=subjects,
                teachers=teachers,
                sessions=[],
                slots=slots,
                classrooms=classrooms,
                generation_options=generation_options or {},
            )
            if diagnostics:
                raise_schedule_generation_diagnostics(
                    diagnostics=diagnostics,
                    detail="Could not generate a feasible schedule with current basic constraints.",
                    code=diagnostics[0]["code"],
                )

        sessions = cls._build_sessions(
            subjects=subjects,
            fallback_teacher=teacher,
        )
        if not sessions:
            raise_schedule_generation_diagnostics(
                diagnostics=collect_generation_diagnostics(
                    subjects=[],
                    teachers=teachers,
                    sessions=[],
                    slots=slots,
                    classrooms=classrooms,
                    generation_options=generation_options or {},
                ),
                detail="Could not generate a feasible schedule with current basic constraints.",
                code="MISSING_SUBJECTS",
            )

        group = _get_or_create_group(actor_email, team)

        rng = random.Random(random_seed)
        cls._randomize_generation_inputs(
            sessions=sessions,
            slots=slots,
            classrooms=classrooms,
            rng=rng,
        )

        diagnostics = collect_generation_diagnostics(
            subjects=subjects,
            teachers=teachers,
            sessions=sessions,
            slots=slots,
            classrooms=classrooms,
            generation_options=generation_options or {},
        )
        blocking = [d for d in diagnostics if d.get("rank", 90) < BOTTLENECK_RANK]
        if blocking:
            raise_schedule_generation_diagnostics(
                diagnostics=blocking,
                detail="Could not generate a feasible schedule with current basic constraints.",
                code=blocking[0]["code"],
            )

        slot_by_session, classroom_by_session, is_optimal, soft_score_info = (
            solve_session_assignment(
                sessions=sessions,
                slots=slots,
                classrooms=classrooms,
                random_seed=random_seed,
                generation_options=generation_options,
            )
        )

        created = []
        timestamp = timezone.now()
        for session_index, slot_index in enumerate(slot_by_session):
            start_time = slots[slot_index]["start"]
            end_time = slots[slot_index]["end"]
            session = sessions[session_index]

            created.append(
                Schedule(
                    name=f"Auto {session['name']} {start_time:%Y-%m-%d %H:%M}",
                    start_time=start_time,
                    end_time=end_time,
                    observations=AUTO_GENERATED_OBSERVATION,
                    team=team,
                    teacher=session["teacher"],
                    classroom=classroom_by_session[session_index],
                    group=session.get("group") or group,
                    subject=session["subject"],
                    created_by=actor_email,
                    updated_by=actor_email,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

        created = cls._bulk_create_generated_schedules(
            schedules=created,
            user=user,
        )

        cls._create_generation_audit_entry(
            schedules=created,
            team=team,
        )
        return created, is_optimal, soft_score_info

    @staticmethod
    def _clear_previous_generated_schedules(*, actor_email: str, user, team):
        """Delete all auto-generated schedules for this user/actor to allow a fresh run.
        Input: actor_email - email of the actor; user - User instance; team - Team instance
        Output: None; side-effect: deletes matching Schedule rows
        """
        with suppress_audit_events(("schedule", AuditActionType.DELETE)):
            Schedule.objects.filter(
                users=user,
                created_by=actor_email,
                observations=AUTO_GENERATED_OBSERVATION,
                team=team,
            ).delete()

    @staticmethod
    def _build_sessions(*, subjects, fallback_teacher):
        """Build the list of session dicts to be scheduled from the subject list.
        Input: subjects - list of Subject instances (with related teacher, group, mandatory_classroom);
               fallback_teacher - Teacher instance used when subjects list is empty
        Output: list of session dicts; empty list if subjects is empty
        """
        if not subjects:
            return []

        sessions = []
        for subject in subjects:
            session_count = max(1, int(subject.weekly_hours))
            for _ in range(session_count):
                sessions.append(
                    {
                        "teacher": subject.teacher,
                        "teacher_id": subject.teacher_id,
                        "group": subject.group,
                        "subject": subject,
                        "allowed_classroom_ids": (
                            {subject.mandatory_classroom_id}
                            if subject.mandatory_classroom_id
                            else set()
                        ),
                        "name": subject.name,
                    }
                )
        return sessions

    @staticmethod
    def _randomize_generation_inputs(*, sessions, slots, classrooms, rng):
        """Shuffle sessions and classrooms in-place to introduce randomness.
        Input: sessions, slots, classrooms - lists to shuffle; rng - seeded Random instance
        Output: None; side-effect: mutates sessions and classrooms order
        """
        rng.shuffle(sessions)
        rng.shuffle(classrooms)

    @staticmethod
    def _bulk_create_generated_schedules(*, schedules, user):
        """Bulk-insert Schedule rows and create the M2M user association.
        Input: schedules - list of unsaved Schedule instances; user - User instance to associate
        Output: list of created Schedule instances with PKs assigned
        """
        if not schedules:
            return []

        created = Schedule.objects.bulk_create(schedules, batch_size=500)
        schedule_user_through = Schedule.users.through
        schedule_user_through.objects.bulk_create(
            [
                schedule_user_through(schedule_id=schedule.id, user_id=user.id)
                for schedule in created
            ],
            batch_size=1000,
        )
        return created

    @staticmethod
    def _create_generation_audit_entry(*, schedules, team):
        """Create a single audit entry summarising the generation run.
        Input: schedules - list of created Schedule instances; team - Team instance
        Output: None; side-effect: writes an audit entry row
        """
        if not schedules:
            return

        create_audit_entry(
            model=Schedule,
            entity_id=schedules[0].id,
            entity_name="Generacion automatica",
            action_type=AuditActionType.CREATE,
            detail=(f"Se generó un horario automatico con {len(schedules)} sesiones."),
            changed_fields=[
                {
                    "campo": "Sesiones generadas",
                    "valor_nuevo": len(schedules),
                }
            ],
            team=team,
        )


# ---------------------------------------------------------------------------
# Replanner
# ---------------------------------------------------------------------------


class ScheduleReplanner:
    """Replan an existing schedule with a fixed manual session-to-slot assignment."""

    @classmethod
    @transaction.atomic
    def replan_with_manual_change(
        cls,
        *,
        user,
        team,
        schedule_to_move_id: int,
        new_slot_index: int,
        actor_email: str,
    ):
        """Replan the full timetable after locking one session to a new slot.
        Input: user - Django User instance; team - Team instance;
               schedule_to_move_id - PK of the Schedule to fix at new_slot_index;
               new_slot_index - target slot index in the weekly slots array;
               actor_email - email of the user initiating the change
        Output: list of updated Schedule instances
        """
        try:
            schedule_to_move = Schedule.objects.select_related(
                "teacher", "classroom", "group", "subject"
            ).get(id=schedule_to_move_id, users=user, team=team)
        except Schedule.DoesNotExist as exc:
            raise ScheduleGenerationError(
                "The selected schedule was not found for the current user.",
                code="SCHEDULE_NOT_FOUND",
                context={"schedule_id": schedule_to_move_id},
            ) from exc

        timetable_schedules = list(
            cls._fetch_timetable_schedules(
                user=user,
                anchor_schedule=schedule_to_move,
                team=team,
            )
        )
        if not timetable_schedules:
            raise ScheduleGenerationError(
                "No schedules found for manual replanning.",
                code="NO_SCHEDULES_FOR_REPLANNING",
            )

        fallback_classroom = _get_or_create_classroom(actor_email, team)
        classrooms = _build_classroom_pool(
            fallback_classroom=fallback_classroom,
            team=team,
        )
        custom_windows = parse_schedule_config_to_slot_windows(
            getattr(team, "schedule_config", None)
        )
        slots = build_weekly_slots(stage_slot_windows=custom_windows)
        slot_index_by_key = {
            slot_instance_key(slot=slot): idx for idx, slot in enumerate(slots)
        }

        if new_slot_index < 0 or new_slot_index >= len(slots):
            raise ScheduleGenerationError(
                f"Invalid slot index {new_slot_index}. Must be 0-{len(slots) - 1}",
                code="INVALID_SLOT_INDEX",
                context={
                    "new_slot_index": new_slot_index,
                    "max_slot_index": len(slots) - 1,
                },
            )

        sessions, previous_assignment_by_session, moved_session_idx = (
            cls._build_replanning_inputs(
                schedules=timetable_schedules,
                moved_schedule_id=schedule_to_move.id,
                slot_index_by_key=slot_index_by_key,
            )
        )

        if moved_session_idx is None:
            raise ScheduleGenerationError(
                f"Could not find schedule {schedule_to_move_id} inside selected timetable.",
                code="SCHEDULE_NOT_FOUND_IN_TIMETABLE",
                context={"schedule_id": schedule_to_move_id},
            )

        fixed_assignments = {moved_session_idx: new_slot_index}

        slot_by_session, classroom_by_session, _, _soft_score = (
            solve_session_assignment(
                sessions=sessions,
                slots=slots,
                classrooms=classrooms,
                random_seed=None,
                fixed_assignments=fixed_assignments,
                previous_assignment_by_session=previous_assignment_by_session,
            )
        )

        return cls._apply_assignment_updates(
            schedules=timetable_schedules,
            sessions=sessions,
            slot_by_session=slot_by_session,
            classroom_by_session=classroom_by_session,
            slots=slots,
            actor_email=actor_email,
            team=team,
        )

    @staticmethod
    def _fetch_timetable_schedules(*, user, anchor_schedule, team):
        """Fetch all schedules in the same timetable as the anchor schedule.
        Input: user - User instance; anchor_schedule - Schedule used as reference;
               team - Team instance
        Output: QuerySet of Schedule instances with related fields pre-selected
        """
        return (
            Schedule.objects.filter(
                users=user,
                observations=anchor_schedule.observations,
                team=team,
            )
            .select_related("teacher", "classroom", "group", "subject")
            .select_related("subject__mandatory_classroom")
            .order_by("start_time", "id")
        )

    @staticmethod
    def _build_replanning_inputs(*, schedules, moved_schedule_id, slot_index_by_key):
        """Build session list and previous assignment map from existing schedules.
        Input: schedules - list of Schedule instances in the timetable;
               moved_schedule_id - PK of the schedule being moved;
               slot_index_by_key - dict {slot_instance_key: slot_idx}
        Output: tuple (sessions, previous_assignment_by_session, moved_session_idx);
                raises ScheduleGenerationError if a schedule cannot be mapped to a slot
        """
        sessions = []
        previous_assignment_by_session = {}
        moved_session_idx = None

        for idx, schedule in enumerate(schedules):
            sessions.append(
                {
                    "teacher": schedule.teacher,
                    "teacher_id": schedule.teacher_id,
                    "group": schedule.group,
                    "subject": schedule.subject,
                    "allowed_classroom_ids": (
                        {schedule.subject.mandatory_classroom_id}
                        if schedule.subject and schedule.subject.mandatory_classroom_id
                        else set()
                    ),
                    "name": getattr(schedule.subject, "name", schedule.name),
                }
            )

            slot_key = slot_instance_key(
                slot={
                    "start": schedule.start_time,
                    "end": schedule.end_time,
                    "stage": session_stage_code(
                        session={
                            "group": schedule.group,
                            "subject": schedule.subject,
                        }
                    ),
                }
            )
            if slot_key not in slot_index_by_key:
                raise ScheduleGenerationError(
                    "Could not map existing schedule slot to current weekly slot model.",
                    code="SLOT_MODEL_MAPPING_FAILED",
                    context={"schedule_id": schedule.id},
                )

            previous_assignment_by_session[idx] = {
                "slot_index": slot_index_by_key[slot_key],
                "classroom_id": schedule.classroom_id,
            }

            if schedule.id == moved_schedule_id:
                moved_session_idx = idx

        return sessions, previous_assignment_by_session, moved_session_idx

    @classmethod
    def _apply_assignment_updates(
        cls,
        *,
        schedules,
        sessions,
        slot_by_session,
        classroom_by_session,
        slots,
        actor_email,
        team,
    ):
        """Persist the new slot/classroom assignment back to each Schedule row.
        Input: schedules - list of Schedule instances; sessions - list of session dicts;
               slot_by_session - list of assigned slot indices (one per session);
               classroom_by_session - list of assigned Classroom instances;
               slots - full slot list; actor_email - email for updated_by; team - Team instance
        Output: list of updated Schedule instances
        """
        updated = []

        for idx, schedule in enumerate(schedules):
            start_time = slots[slot_by_session[idx]]["start"]
            end_time = slots[slot_by_session[idx]]["end"]
            session = sessions[idx]
            observation = (schedule.observations or "").strip()

            if observation == AUTO_GENERATED_OBSERVATION:
                schedule.name = f"Auto {session['name']} {start_time:%Y-%m-%d %H:%M}"

            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.teacher = session["teacher"]
            schedule.group = session.get("group") or _get_or_create_group(
                actor_email,
                team,
            )
            schedule.subject = session["subject"]
            schedule.classroom = classroom_by_session[idx]
            schedule.updated_by = actor_email
            schedule.save()
            updated.append(schedule)

        return updated
