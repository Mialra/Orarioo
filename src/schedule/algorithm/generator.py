from datetime import timedelta

from django.db import transaction

from classroom.models import Classroom
from group.models import EducationalStage, Group
from schedule.algorithm.assignment import solve_session_assignment
from schedule.algorithm.constraints import validate_group_and_teacher_capacity
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import build_weekly_slots
from schedule.models import Schedule
from subject.models import Subject
from teacher.models import Teacher


class BasicScheduleGenerator:

    @classmethod
    @transaction.atomic
    def generate(cls, *, actor_email: str, user):
        cls._clear_previous_generated_schedules(actor_email=actor_email, user=user)

        teacher = Teacher.objects.order_by("id").first()
        if teacher is None:
            raise ScheduleGenerationError(
                "At least one teacher is required before generating a schedule."
            )

        fallback_classroom = cls._get_or_create_classroom(actor_email)
        group = cls._get_or_create_group(actor_email)
        subjects = list(
            Subject.objects.select_related("teacher", "group").order_by("id")
        )
        classroom_by_group_id = cls._build_group_classroom_map(
            subjects=subjects,
            fallback_classroom=fallback_classroom,
        )
        sessions = cls._build_sessions(subjects=subjects, fallback_teacher=teacher)
        slots = build_weekly_slots()

        validate_group_and_teacher_capacity(sessions=sessions, slots=slots)

        slot_by_session = solve_session_assignment(sessions=sessions, slots=slots)

        created = []
        for session_index, slot_index in enumerate(slot_by_session):
            start_time = slots[slot_index]
            end_time = start_time + timedelta(hours=1)
            session = sessions[session_index]

            schedule = Schedule.objects.create(
                name=f"Auto {session['name']} {start_time:%Y-%m-%d %H:%M}",
                start_time=start_time,
                end_time=end_time,
                observations="Auto-generated with CP-SAT basic constraints.",
                teacher=session["teacher"],
                classroom=classroom_by_group_id.get(
                    getattr(session.get("group"), "id", None),
                    fallback_classroom,
                ),
                group=session.get("group") or group,
                subject=session["subject"],
                created_by=actor_email,
                updated_by=actor_email,
            )
            schedule.users.add(user)
            created.append(schedule)

        return created

    @staticmethod
    def _clear_previous_generated_schedules(*, actor_email: str, user):
        """Clean previous generated schedules to keep a single timetable view per run."""
        Schedule.objects.filter(
            users=user,
            created_by=actor_email,
            observations="Auto-generated with CP-SAT basic constraints.",
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
                        "name": subject.name,
                    }
                )
        return sessions

    @staticmethod
    def _get_or_create_classroom(actor_email: str):
        classroom = Classroom.objects.order_by("id").first()
        if classroom is not None:
            return classroom
        return Classroom.objects.create(
            name="Auto Classroom",
            created_by=actor_email,
            updated_by=actor_email,
        )

    @staticmethod
    def _get_or_create_group(actor_email: str):
        group = Group.objects.order_by("id").first()
        if group is not None:
            return group
        return Group.objects.create(
            name="Auto Group",
            stage=EducationalStage.PRIMARY,
            created_by=actor_email,
            updated_by=actor_email,
        )

    @staticmethod
    def _build_group_classroom_map(*, subjects, fallback_classroom):
        """Map each subject group to its most suitable classroom by name."""
        mapping = {}
        groups = {
            subject.group for subject in subjects if getattr(subject, "group", None)
        }

        for group in groups:
            classroom = (
                Classroom.objects.filter(name__icontains=group.name)
                .order_by("id")
                .first()
            )
            if classroom is None:
                classroom = fallback_classroom
            mapping[group.id] = classroom

        return mapping
