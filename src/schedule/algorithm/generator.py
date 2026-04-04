import random

from django.db import transaction

from classroom.models import Classroom
from group.models import EducationalStage, Group
from schedule.algorithm.assignment import solve_session_assignment
from schedule.algorithm.constraints import validate_group_and_teacher_capacity
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import (
    build_weekly_slots,
    session_stage_code,
    slot_instance_key,
)
from schedule.constants import AUTO_GENERATED_OBSERVATION
from schedule.models import Schedule
from subject.models import Subject
from teacher.models import Teacher


class BasicScheduleGenerator:

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
        cls._clear_previous_generated_schedules(
            actor_email=actor_email,
            user=user,
            team=team,
        )

        teacher = Teacher.objects.filter(team=team).order_by("id").first()
        if teacher is None:
            raise ScheduleGenerationError(
                "At least one teacher is required before generating a schedule."
            )

        fallback_classroom = cls._get_or_create_classroom(actor_email, team)
        group = cls._get_or_create_group(actor_email, team)
        subjects = list(
            Subject.objects.filter(team=team)
            .select_related("teacher", "group")
            .prefetch_related("allowed_classrooms")
            .order_by("id")
        )
        classrooms = cls._build_classroom_pool(
            fallback_classroom=fallback_classroom,
            team=team,
        )
        sessions = cls._build_sessions(subjects=subjects, fallback_teacher=teacher)
        slots = build_weekly_slots()

        rng = random.Random(random_seed)
        cls._randomize_generation_inputs(
            sessions=sessions,
            slots=slots,
            classrooms=classrooms,
            rng=rng,
        )

        validate_group_and_teacher_capacity(
            sessions=sessions,
            slots=slots,
            generation_options=generation_options,
        )

        slot_by_session, classroom_by_session = solve_session_assignment(
            sessions=sessions,
            slots=slots,
            classrooms=classrooms,
            random_seed=random_seed,
        )

        created = []
        for session_index, slot_index in enumerate(slot_by_session):
            start_time = slots[slot_index]["start"]
            end_time = slots[slot_index]["end"]
            session = sessions[session_index]

            schedule = Schedule.objects.create(
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
            )
            schedule.users.add(user)
            created.append(schedule)

        return created

    @staticmethod
    def _clear_previous_generated_schedules(*, actor_email: str, user, team):
        """Clean previous generated schedules to keep a single timetable view per run."""
        Schedule.objects.filter(
            users=user,
            created_by=actor_email,
            observations=AUTO_GENERATED_OBSERVATION,
            team=team,
        ).delete()

    @staticmethod
    def _build_sessions(*, subjects, fallback_teacher):
        sessions = []
        if not subjects:
            return [
                {
                    "teacher": fallback_teacher,
                    "teacher_id": fallback_teacher.id,
                    "subject": None,
                    "name": "Session",
                }
            ]

        for subject in subjects:
            session_count = max(1, int(subject.weekly_hours))
            for _ in range(session_count):
                sessions.append(
                    {
                        "teacher": subject.teacher,
                        "teacher_id": subject.teacher_id,
                        "group": subject.group,
                        "subject": subject,
                        "allowed_classroom_ids": set(
                            subject.allowed_classrooms.values_list("id", flat=True)
                        ),
                        "name": subject.name,
                    }
                )
        return sessions

    @staticmethod
    def _get_or_create_classroom(actor_email: str, team):
        classroom = Classroom.objects.filter(team=team).order_by("id").first()
        if classroom is not None:
            return classroom
        return Classroom.objects.create(
            name="Auto Classroom",
            team=team,
            created_by=actor_email,
            updated_by=actor_email,
        )

    @staticmethod
    def _get_or_create_group(actor_email: str, team):
        group = Group.objects.filter(team=team).order_by("id").first()
        if group is not None:
            return group
        return Group.objects.create(
            name="Auto Group",
            stage=EducationalStage.PRIMARY,
            team=team,
            created_by=actor_email,
            updated_by=actor_email,
        )

    @staticmethod
    def _build_classroom_pool(*, fallback_classroom, team):
        classrooms = list(Classroom.objects.filter(team=team).order_by("id"))
        if not classrooms:
            return [fallback_classroom]
        return classrooms

    @staticmethod
    def _randomize_generation_inputs(*, sessions, slots, classrooms, rng):
        rng.shuffle(sessions)
        rng.shuffle(classrooms)


class ScheduleReplanner:
    """Replan an existing schedule with manual session-to-slot changes."""

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
        """Replan schedule with a fixed session assignment.

        Args:
            user: Django user object
            schedule_to_move_id: ID of the Schedule to move to new_slot_index
            new_slot_index: Target slot index in the weekly slots array
            actor_email: Email of the user initiating the change

        Returns:
            List of newly created Schedules
        """
        try:
            schedule_to_move = Schedule.objects.select_related(
                "teacher", "classroom", "group", "subject"
            ).get(id=schedule_to_move_id, users=user, team=team)
        except Schedule.DoesNotExist as exc:
            raise ScheduleGenerationError(
                "The selected schedule was not found for the current user."
            ) from exc

        timetable_schedules = list(
            cls._fetch_timetable_schedules(
                user=user,
                anchor_schedule=schedule_to_move,
                team=team,
            )
        )
        if not timetable_schedules:
            raise ScheduleGenerationError("No schedules found for manual replanning.")

        fallback_classroom = cls._get_or_create_classroom(actor_email, team)
        classrooms = cls._build_classroom_pool(
            fallback_classroom=fallback_classroom,
            team=team,
        )
        slots = build_weekly_slots()
        slot_index_by_key = {
            slot_instance_key(slot=slot): idx for idx, slot in enumerate(slots)
        }

        if new_slot_index < 0 or new_slot_index >= len(slots):
            raise ScheduleGenerationError(
                f"Invalid slot index {new_slot_index}. Must be 0-{len(slots) - 1}"
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
                f"Could not find schedule {schedule_to_move_id} inside selected timetable."
            )

        fixed_assignments = {moved_session_idx: new_slot_index}

        slot_by_session, classroom_by_session = solve_session_assignment(
            sessions=sessions,
            slots=slots,
            classrooms=classrooms,
            random_seed=None,
            fixed_assignments=fixed_assignments,
            previous_assignment_by_session=previous_assignment_by_session,
        )

        return cls._apply_assignment_updates(
            schedules=timetable_schedules,
            sessions=sessions,
            slot_by_session=slot_by_session,
            classroom_by_session=classroom_by_session,
            slots=slots,
            actor_email=actor_email,
        )

    @staticmethod
    def _get_or_create_classroom(actor_email: str, team):
        classroom = Classroom.objects.filter(team=team).order_by("id").first()
        if classroom is not None:
            return classroom
        return Classroom.objects.create(
            name="Auto Classroom",
            team=team,
            created_by=actor_email,
            updated_by=actor_email,
        )

    @staticmethod
    def _get_or_create_group(actor_email: str, team):
        group = Group.objects.filter(team=team).order_by("id").first()
        if group is not None:
            return group
        return Group.objects.create(
            name="Auto Group",
            stage=EducationalStage.PRIMARY,
            team=team,
            created_by=actor_email,
            updated_by=actor_email,
        )

    @staticmethod
    def _build_classroom_pool(*, fallback_classroom, team):
        classrooms = list(Classroom.objects.filter(team=team).order_by("id"))
        if not classrooms:
            return [fallback_classroom]
        return classrooms

    @staticmethod
    def _fetch_timetable_schedules(*, user, anchor_schedule, team):
        return (
            Schedule.objects.filter(
                users=user,
                observations=anchor_schedule.observations,
                team=team,
            )
            .select_related("teacher", "classroom", "group", "subject")
            .order_by("start_time", "id")
        )

    @staticmethod
    def _build_replanning_inputs(*, schedules, moved_schedule_id, slot_index_by_key):
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
                    "Could not map existing schedule slot to current weekly slot model."
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
    ):
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
            schedule.group = session.get("group") or cls._get_or_create_group(
                actor_email
            )
            schedule.subject = session["subject"]
            schedule.classroom = classroom_by_session[idx]
            schedule.updated_by = actor_email
            schedule.save()
            updated.append(schedule)

        return updated
