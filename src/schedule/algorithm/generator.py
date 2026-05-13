"""Schedule generator using the CP-SAT constraint solver.

BasicScheduleGenerator creates a full weekly timetable from scratch.
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
from schedule.algorithm.slots import (
    build_weekly_slots,
    parse_schedule_config_to_slot_windows,
)
from schedule.algorithm.tc_assigner import assign_tc_sessions
from schedule.constants import AUTO_GENERATED_OBSERVATION, SAVED_TIMETABLE_PREFIX
from schedule.models import Schedule, TCSession
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

        teachers_on_duty = generation_options.get("teachers_on_duty", 0)
        tc_result = None
        if teachers_on_duty > 0:
            tc_result = assign_tc_sessions(
                teachers=teachers,
                existing_schedules=created,
                weekly_slots=slots,
                teachers_on_duty=teachers_on_duty,
                team=team,
            )

        created = cls._bulk_create_generated_schedules(
            schedules=created,
            user=user,
        )

        TCSession.objects.filter(team=team).exclude(
            observations__startswith=SAVED_TIMETABLE_PREFIX
        ).delete()
        if tc_result and tc_result.tc_sessions:
            TCSession.objects.bulk_create(tc_result.tc_sessions)

        cls._create_generation_audit_entry(
            schedules=created,
            team=team,
        )
        return created, is_optimal, soft_score_info, tc_result

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
            detail=(
                f"Se generó el horario {schedules[0].name} con {len(schedules)} sesiones."
            ),
            changed_fields=[
                {
                    "campo": "Sesiones generadas",
                    "valor_nuevo": len(schedules),
                }
            ],
            team=team,
        )
