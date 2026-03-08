from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - depends on local Python version
    cp_model = None

from classroom.models import Classroom
from group.models import EducationalStage, Group
from schedule.models import Schedule
from subject.models import Subject
from teacher.models import Teacher


class ScheduleGenerationError(Exception):
    """Raised when a schedule cannot be generated with current data."""


class BasicScheduleGenerator:
    """Basic CP-SAT generator with non-overlap rules for teacher and group."""

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
        slots = cls._build_slots()

        cls._validate_capacity(sessions=sessions, slots=slots)

        slot_by_session = cls._solve_session_assignment(sessions=sessions, slots=slots)

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
    def _build_slots():
        """
        Build time slots for ESO schedule: 8:30-15:00 with 6 hours/day.
        Schedule: 3 hours (8:30-11:30), break (11:30-12:00), 3 hours (12:00-15:00)

        Each slot can accommodate multiple groups simultaneously (different classrooms),
        so we generate enough slots for all sessions across all groups.
        """
        now = timezone.localtime()
        # Build a clean weekly timetable in the next Monday-Friday window.
        days_until_next_monday = (7 - now.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7
        start_day = now.date() + timedelta(days=days_until_next_monday)
        slots = []
        day_cursor = start_day

        # Define hourly slots: before break and after break
        morning_start_times = [
            time(hour=8, minute=30),  # 8:30-9:30
            time(hour=9, minute=30),  # 9:30-10:30
            time(hour=10, minute=30),  # 10:30-11:30
        ]
        afternoon_start_times = [
            time(hour=12, minute=0),  # 12:00-13:00
            time(hour=13, minute=0),  # 13:00-14:00
            time(hour=14, minute=0),  # 14:00-15:00
        ]

        # Exactly one school week: 5 days x 6 sessions = 30 slots.
        for _ in range(5):
            # Morning slots (before break 11:30-12:00)
            for start_time_obj in morning_start_times:
                slots.append(
                    timezone.make_aware(
                        datetime.combine(day_cursor, start_time_obj),
                        timezone.get_current_timezone(),
                    )
                )

            # Afternoon slots (after break)
            for start_time_obj in afternoon_start_times:
                slots.append(
                    timezone.make_aware(
                        datetime.combine(day_cursor, start_time_obj),
                        timezone.get_current_timezone(),
                    )
                )

            day_cursor += timedelta(days=1)

        return slots

    @staticmethod
    def _validate_capacity(*, sessions, slots):
        """Validate weekly capacity considering that groups can run in parallel."""
        slot_count = len(slots)
        sessions_by_group = {}

        for session in sessions:
            group = session.get("group")
            group_key = getattr(group, "id", None)
            sessions_by_group[group_key] = sessions_by_group.get(group_key, 0) + 1

        if any(
            group_sessions > slot_count for group_sessions in sessions_by_group.values()
        ):
            raise ScheduleGenerationError(
                "Not enough available slots to place all sessions for at least one group."
            )

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
    def _solve_session_assignment(*, sessions, slots):
        if cp_model is None:
            return BasicScheduleGenerator._greedy_session_assignment(
                sessions=sessions,
                slots=slots,
            )

        model = cp_model.CpModel()
        session_count = len(sessions)
        slot_count = len(slots)

        x = BasicScheduleGenerator._build_decision_variables(
            model=model,
            session_count=session_count,
            slot_count=slot_count,
        )
        BasicScheduleGenerator._add_exactly_one_slot_constraints(
            model=model,
            x=x,
            session_count=session_count,
            slot_count=slot_count,
        )
        BasicScheduleGenerator._add_resource_non_overlap_constraints(
            model=model,
            x=x,
            sessions=sessions,
            slot_count=slot_count,
            resource_key="teacher_id",
        )
        BasicScheduleGenerator._add_resource_non_overlap_constraints(
            model=model,
            x=x,
            sessions=sessions,
            slot_count=slot_count,
            resource_key="group_id",
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise ScheduleGenerationError(
                "Could not generate a feasible schedule with current basic constraints."
            )

        return BasicScheduleGenerator._extract_slot_assignment(
            solver=solver,
            x=x,
            session_count=session_count,
            slot_count=slot_count,
        )

    @staticmethod
    def _build_decision_variables(*, model, session_count, slot_count):
        x = {}
        for s_idx in range(session_count):
            for p_idx in range(slot_count):
                x[(s_idx, p_idx)] = model.NewBoolVar(f"x_s{s_idx}_p{p_idx}")
        return x

    @staticmethod
    def _add_exactly_one_slot_constraints(*, model, x, session_count, slot_count):
        for s_idx in range(session_count):
            model.Add(sum(x[(s_idx, p_idx)] for p_idx in range(slot_count)) == 1)

    @staticmethod
    def _session_resource_id(*, session, resource_key):
        if resource_key == "group_id":
            group = session.get("group")
            return getattr(group, "id", None)
        return session.get(resource_key)

    @staticmethod
    def _add_resource_non_overlap_constraints(
        *, model, x, sessions, slot_count, resource_key
    ):
        resource_to_sessions = {}
        for idx, session in enumerate(sessions):
            resource_id = BasicScheduleGenerator._session_resource_id(
                session=session,
                resource_key=resource_key,
            )
            if resource_id is None:
                continue
            resource_to_sessions.setdefault(resource_id, []).append(idx)

        for resource_sessions in resource_to_sessions.values():
            for p_idx in range(slot_count):
                model.Add(sum(x[(s_idx, p_idx)] for s_idx in resource_sessions) <= 1)

    @staticmethod
    def _extract_slot_assignment(*, solver, x, session_count, slot_count):
        slot_by_session = []
        for s_idx in range(session_count):
            selected = None
            for p_idx in range(slot_count):
                if solver.Value(x[(s_idx, p_idx)]) == 1:
                    selected = p_idx
                    break
            if selected is None:
                raise ScheduleGenerationError(
                    "Solver returned an incomplete assignment."
                )
            slot_by_session.append(selected)

        return slot_by_session

    @staticmethod
    def _greedy_session_assignment(*, sessions, slots):
        teacher_busy_slots = {}
        group_busy_slots = {}
        slot_by_session = []

        for s_idx, session in enumerate(sessions):
            teacher_id = session["teacher_id"]
            teacher_busy_slots.setdefault(teacher_id, set())

            group = session.get("group")
            group_id = group.id if group else None
            if group_id:
                group_busy_slots.setdefault(group_id, set())

            selected_slot = None
            for p_idx in range(len(slots)):
                if p_idx in teacher_busy_slots[teacher_id]:
                    continue
                if group_id and p_idx in group_busy_slots[group_id]:
                    continue
                selected_slot = p_idx
                break

            if selected_slot is None:
                raise ScheduleGenerationError(
                    "Could not generate a feasible schedule with current basic constraints."
                )

            slot_by_session.append(selected_slot)
            teacher_busy_slots[teacher_id].add(selected_slot)
            if group_id:
                group_busy_slots[group_id].add(selected_slot)

        return slot_by_session

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
