"""Post-generation schedule evaluator for detecting non-critical defects.

Analyses generated schedules for internal and structural gaps within each
group's daily timetable block. Runs after generation and never prevents
the process from completing.
"""

import logging
from collections import defaultdict

from django.utils import timezone

logger = logging.getLogger(__name__)

# Time windows per educational stage (breaks excluded).
# NOTE: 'end' is the LAST CLASS HOUR, not the end of the school day.
# Example: for a 9:00-14:00 day the last class starts at 13:00 (hour 13).
STAGE_HOURS = {
    "preschool": {
        "name": "Infantil",
        "start": 9,  # First class at 9:00
        "end": 13,  # Last class 13:00-14:00
        "break": (10.5, 11),  # 10:30-11:00
    },
    "primary": {
        "name": "Primaria",
        "start": 9,  # First class at 9:00
        "end": 13,  # Last class 13:00-14:00
        "break": (11.5, 12),  # 11:30-12:00
    },
    "secondary": {
        "name": "ESO",
        "start": 8,  # First class at 8:00
        "end": 13,  # Last class 13:30-14:30 (modelled as hour 13)
        "break": (11, 11.5),  # 11:00-11:30
    },
}


class ScheduleEvaluator:
    """Analyses generated schedules to detect non-critical defects.

    Runs AFTER generation; never fails the generation process.
    """

    @staticmethod
    def get_expected_hours_for_stage(stage):
        """Return the set of expected teaching hours for a stage, excluding breaks.
        Input: stage - 'preschool', 'primary', or 'secondary'
        Output: set of integers representing the start hour of each teaching period
        """
        config = STAGE_HOURS.get(stage)
        if not config:
            config = STAGE_HOURS["primary"]

        start = int(config["start"])
        end = int(config["end"])
        break_start = config["break"][0]
        break_end = config["break"][1]

        expected = set()
        for hour in range(start, end + 1):
            if break_start <= hour < break_end:
                continue
            expected.add(hour)

        return expected

    @staticmethod
    def _build_sessions_by_group_day(schedules):
        """Group schedules by group + date and collect occupied hours and stage.
        Input: schedules - queryset or list of Schedule objects
        Output: dict {group_day_key: {group, group_name, date, hours, stage}}
        """
        sessions_by_group_day = defaultdict(
            lambda: {
                "group": None,
                "group_name": "",
                "date": "",
                "hours": set(),
                "stage": None,
            }
        )

        processed = 0
        skipped = 0

        for schedule in schedules:
            if not schedule.group or not schedule.start_time:
                skipped += 1
                continue

            processed += 1

            local_start = timezone.localtime(schedule.start_time)
            date_key = local_start.strftime("%Y-%m-%d")
            hour = local_start.hour

            group_day_key = f"{schedule.group.id}_{date_key}"

            sessions_by_group_day[group_day_key]["group"] = schedule.group
            sessions_by_group_day[group_day_key]["group_name"] = schedule.group.name
            sessions_by_group_day[group_day_key]["date"] = date_key
            sessions_by_group_day[group_day_key]["hours"].add(hour)

            try:
                stage = (
                    schedule.group.stage
                    if hasattr(schedule.group, "stage")
                    else "primary"
                )
            except Exception as e:
                logger.debug("Error getting stage: %s", e)
                stage = "primary"
            sessions_by_group_day[group_day_key]["stage"] = stage

        logger.info(
            "Processed: %d, Skipped: %d, Group-day combinations: %d",
            processed,
            skipped,
            len(sessions_by_group_day),
        )
        return sessions_by_group_day

    @staticmethod
    def _detect_internal_gaps(day_data, hours_list, expected_hours):
        """Detect internal gaps between consecutive sessions of a group on a given day.
        Input: day_data - dict with group/date info;
               hours_list - sorted list of occupied hours;
               expected_hours - set of expected hours for the stage
        Output: list of defect dicts with gap_type='INTERNAL'
        """
        defects = []

        for i in range(len(hours_list) - 1):
            current_hour = hours_list[i]
            next_hour = hours_list[i + 1]

            if next_hour - current_hour > 1:
                for missing_hour in range(current_hour + 1, next_hour):
                    if missing_hour in expected_hours:
                        defect = {
                            "entity_id": day_data["group"].id,
                            "entity_name": day_data["group_name"],
                            "entity_type": "group",
                            "severity": "MEDIUM",
                            "gap_type": "INTERNAL",
                            "description": (
                                f"{day_data['group_name']} - {day_data['date']} "
                                f"{str(missing_hour).zfill(2)}:00: Hueco detectado"
                            ),
                            "context": {
                                "date": day_data["date"],
                                "hour": missing_hour,
                                "hours_occupied": hours_list,
                                "stage": day_data["stage"],
                            },
                        }
                        defects.append(defect)
                        logger.info("DEFECT INTERNAL: %s", defect["description"])

        return defects

    @staticmethod
    def _detect_boundary_gaps(
        day_data, hours_set, hours_list, expected_hours, stage_config, stage
    ):
        """Detect missing hours within the expected range for the stage (boundary gaps).
        Input: day_data - dict with group/date info;
               hours_set - set of occupied hours;
               hours_list - sorted list of occupied hours;
               expected_hours - set of expected hours for the stage;
               stage_config - stage configuration dict from STAGE_HOURS;
               stage - stage identifier string ('preschool', 'primary', 'secondary')
        Output: list of defect dicts with gap_type='BOUNDARY'
        """
        defects = []
        missing_expected_hours = expected_hours - hours_set

        if missing_expected_hours:
            for missing_hour in sorted(missing_expected_hours):
                defect = {
                    "entity_id": day_data["group"].id,
                    "entity_name": day_data["group_name"],
                    "entity_type": "group",
                    "severity": "LOW",
                    "gap_type": "BOUNDARY",
                    "description": (
                        f"{day_data['group_name']} - {day_data['date']} "
                        f"{str(missing_hour).zfill(2)}:00: Sesión faltante"
                    ),
                    "context": {
                        "date": day_data["date"],
                        "hour": missing_hour,
                        "hours_occupied": hours_list,
                        "expected_range": f"{int(stage_config['start'])}:00 - {stage_config['end']}:00",
                        "stage": stage,
                    },
                }
                defects.append(defect)
                logger.info("DEFECT BOUNDARY: %s", defect["description"])

        return defects

    @staticmethod
    def analyze_gaps_groups(schedules):
        """Detect internal and structural gaps within each group's daily timetable block.

        Detects two gap types:
        1. Internal: between consecutive sessions (e.g. 9:00 → 11:00, 10:00 missing).
        2. Boundary: missing hours relative to the expected range for the stage.

        Input: schedules - queryset or list of Schedule objects
        Output: list of defect dicts for all detected gaps
        """
        logger.info("analyze_gaps_groups: Analysing %d schedules", len(schedules))

        sessions_by_group_day = ScheduleEvaluator._build_sessions_by_group_day(
            schedules
        )

        defects = []

        for _group_day_key, day_data in sessions_by_group_day.items():
            if not day_data["hours"]:
                continue

            stage = day_data["stage"] or "primary"
            expected_hours = ScheduleEvaluator.get_expected_hours_for_stage(stage)
            stage_config = STAGE_HOURS.get(stage, STAGE_HOURS["primary"])

            hours_set = day_data["hours"]
            hours_list = sorted(hours_set)

            defects.extend(
                ScheduleEvaluator._detect_internal_gaps(
                    day_data, hours_list, expected_hours
                )
            )

            defects.extend(
                ScheduleEvaluator._detect_boundary_gaps(
                    day_data, hours_set, hours_list, expected_hours, stage_config, stage
                )
            )

        logger.info("analyze_gaps_groups: Detected %d gaps", len(defects))
        return defects

    @staticmethod
    def analyze_exact_hours_teachers(schedules):
        """Detect teachers in exact-hours mode whose total assigned time doesn't match target.

        Sums the actual duration of every session assigned to each exact-mode teacher
        (regular + TC) and compares against max_weekly_hours * 60 + max_weekly_minutes.

        Input: schedules - queryset or list of Schedule objects
        Output: list of defect dicts for teachers with unmet exact workloads
        """
        teacher_minutes = defaultdict(float)
        teacher_obj = {}

        for schedule in schedules:
            teacher = getattr(schedule, "teacher", None)
            if teacher is None:
                continue
            if not getattr(teacher, "weekly_hours_exact", False):
                continue
            start = schedule.start_time
            end = schedule.end_time
            if start is None or end is None:
                continue
            teacher_minutes[teacher.id] += (end - start).total_seconds() / 60.0
            teacher_obj[teacher.id] = teacher

        defects = []
        for tid, teacher in teacher_obj.items():
            target = (getattr(teacher, "max_weekly_hours", 0) or 0) * 60 + (
                getattr(teacher, "max_weekly_minutes", 0) or 0
            )
            assigned = teacher_minutes[tid]
            if abs(assigned - target) < 0.5:
                continue
            target_h, target_m = divmod(int(target), 60)
            assigned_h, assigned_m = divmod(int(round(assigned)), 60)
            target_str = f"{target_h} h {target_m} min" if target_m else f"{target_h} h"
            assigned_str = (
                f"{assigned_h} h {assigned_m} min" if assigned_m else f"{assigned_h} h"
            )
            defects.append(
                {
                    "entity_id": tid,
                    "entity_name": teacher.name,
                    "entity_type": "teacher",
                    "severity": "HIGH",
                    "gap_type": "EXACT_HOURS_NOT_MET",
                    "description": (
                        f"Carga exacta no cumplida: {assigned_str} asignadas, "
                        f"objetivo {target_str}"
                    ),
                    "context": {
                        "teacher_id": tid,
                        "teacher_name": teacher.name,
                        "target_minutes": int(target),
                        "assigned_minutes": int(round(assigned)),
                        "target_hours": target_h,
                        "target_extra_minutes": target_m,
                        "assigned_hours": assigned_h,
                        "assigned_extra_minutes": assigned_m,
                    },
                }
            )
        return defects

    @staticmethod
    def _fmt_minutes(total_minutes):
        h, m = divmod(int(total_minutes), 60)
        return f"{h} h {m} min" if m else f"{h} h"

    @staticmethod
    def _accumulate_schedule_minutes(schedules, teacher_minutes, teacher_obj):
        for schedule in schedules:
            teacher = getattr(schedule, "teacher", None)
            if not teacher or not getattr(teacher, "max_weekly_hours", None):
                continue
            start, end = schedule.start_time, schedule.end_time
            if start is None or end is None:
                continue
            teacher_minutes[teacher.id] += (end - start).total_seconds() / 60.0
            teacher_obj[teacher.id] = teacher

    @staticmethod
    def _accumulate_tc_minutes(tc_sessions, teacher_minutes, teacher_obj):
        for tc in tc_sessions or []:
            teacher = getattr(tc, "teacher", None)
            if not teacher or not getattr(teacher, "max_weekly_hours", None):
                continue
            start_t, end_t = tc.start_time, tc.end_time
            if start_t is None or end_t is None:
                continue
            duration = (end_t.hour * 60 + end_t.minute) - (
                start_t.hour * 60 + start_t.minute
            )
            if duration > 0:
                teacher_minutes[teacher.id] += duration
                teacher_obj[teacher.id] = teacher

    @staticmethod
    def _build_overload_defect(tid, teacher, assigned, limit):
        return {
            "entity_id": tid,
            "entity_name": teacher.name,
            "entity_type": "teacher",
            "severity": "HIGH",
            "gap_type": "MAX_HOURS_EXCEEDED",
            "description": (
                f"Carga máxima superada: "
                f"{ScheduleEvaluator._fmt_minutes(round(assigned))} asignadas, "
                f"máximo {ScheduleEvaluator._fmt_minutes(limit)}"
            ),
            "context": {
                "teacher_id": tid,
                "teacher_name": teacher.name,
                "limit_minutes": int(limit),
                "assigned_minutes": int(round(assigned)),
            },
        }

    @staticmethod
    def analyze_overloaded_teachers(schedules, tc_sessions=None):
        """Detect teachers whose assigned hours (Schedule + TCSession) exceed max_weekly_hours.

        Input: schedules   - queryset or list of Schedule objects
               tc_sessions - optional list of TCSession objects for the same team
        Output: list of HIGH-severity defect dicts for teachers over the limit
        """
        teacher_minutes = defaultdict(float)
        teacher_obj = {}
        ScheduleEvaluator._accumulate_schedule_minutes(
            schedules, teacher_minutes, teacher_obj
        )
        ScheduleEvaluator._accumulate_tc_minutes(
            tc_sessions, teacher_minutes, teacher_obj
        )

        defects = []
        for tid, teacher in teacher_obj.items():
            limit = (getattr(teacher, "max_weekly_hours", 0) or 0) * 60 + (
                getattr(teacher, "max_weekly_minutes", 0) or 0
            )
            assigned = teacher_minutes[tid]
            if assigned <= limit + 0.5:
                continue
            defects.append(
                ScheduleEvaluator._build_overload_defect(tid, teacher, assigned, limit)
            )
        return defects

    @staticmethod
    def analyze_schedules(schedules, tc_sessions=None):
        """Orchestrate the full analysis of a set of schedules.

        Calls specialised sub-functions to detect different defect types and
        returns the consolidated list. Does not raise on defects found.

        Input: schedules   - queryset or list of Schedule objects
               tc_sessions - optional list of TCSession objects for the same team
        Output: consolidated list of defect dicts; empty list if schedules is empty
        """
        logger.info(
            "=== analyze_schedules START - Total schedules: %d ===",
            len(schedules) if schedules else 0,
        )

        if not schedules:
            logger.warning("No schedules provided")
            return []

        all_defects = []

        gaps_defects = ScheduleEvaluator.analyze_gaps_groups(schedules)
        all_defects.extend(gaps_defects)

        exact_hours_defects = ScheduleEvaluator.analyze_exact_hours_teachers(schedules)
        all_defects.extend(exact_hours_defects)

        overloaded_defects = ScheduleEvaluator.analyze_overloaded_teachers(
            schedules, tc_sessions=tc_sessions
        )
        all_defects.extend(overloaded_defects)

        logger.info(
            "=== analyze_schedules END - Total defects: %d ===", len(all_defects)
        )
        return all_defects
