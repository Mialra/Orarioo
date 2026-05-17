"""ScheduleViewSet and supporting instance methods for the schedule app.

Export, generation option parsing, and move/swap helpers live in the
views_export, views_generate and views_move modules respectively.
"""

import logging
import random
import threading

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from auditableEntity.audit import create_audit_entry, suppress_audit_events
from auditableEntity.models import AuditActionType
from classroom.models import Classroom
from common.drf import TeamScopedAuditableModelViewSet
from common.errors.exceptions import ValidationAppError
from group.models import Group
from schedule.algorithm.evaluator import ScheduleEvaluator
from schedule.algorithm.slots import parse_schedule_config_to_slot_windows
from schedule.constants import AUTO_GENERATED_OBSERVATION, SAVED_TIMETABLE_PREFIX
from schedule.models import Schedule, ScheduleGenerationJob
from schedule.serializers import ScheduleSerializer
from schedule.views_export import (
    _DAY_ORDER,
    build_csv_response_for_schedule,
    build_excel_response,
    build_export_filename,
    build_export_rows,
    build_export_units,
    build_pdf_units_response,
    build_tc_export_rows,
    build_teacher_workloads,
    resolve_saved_schedule_name,
)
from schedule.views_generate import (
    parse_bool_param,
    parse_generation_options,
    parse_positive_int,
)
from schedule.views_move import (
    WEEKDAY_TO_DAY_NAME,
    build_affected_slot_descriptors,
    build_move_assignments,
    is_no_changes_move,
    normalize_move_mode,
    parse_move_slot,
    resolve_slot_datetimes_for_source_week,
    validate_minimal_move_constraints,
)
from subject.models import SubjectTimePreferenceState
from teacher.models import Teacher, TeacherTimePreferenceState
from user.models import User

logger = logging.getLogger(__name__)


def build_stage_windows_for_client(schedule_config=None):
    """Return allowed HH:MM slot ranges per stage for client-side validation.
    Keys use Group.stage values (lowercase) to match group_stage in session serializer.
    Output: dict {group_stage_str: [["HH:MM", "HH:MM"], ...]}
    """
    from common.stages import GROUP_STAGE_TO_CANONICAL
    from schedule.algorithm.slots import (
        STAGE_SLOT_WINDOWS,
        parse_schedule_config_to_slot_windows,
    )

    slot_windows = (
        parse_schedule_config_to_slot_windows(schedule_config) or STAGE_SLOT_WINDOWS
    )
    canonical_to_group = {str(v): k for k, v in GROUP_STAGE_TO_CANONICAL.items()}
    result = {}
    for stage, windows in slot_windows.items():
        key = canonical_to_group.get(str(stage), str(stage))
        result[key] = [
            [w[0].strftime("%H:%M"), w[1].strftime("%H:%M")] for w in windows
        ]
    return result


def build_unavailability_index(schedules):
    """Build a dict of UNAVAILABLE slot keys per teacher and subject for client-side pre-validation.
    Input: schedules - list of Schedule instances with teacher and subject select_related
    Output: dict {"teachers": {str(id): [slot_key, ...]}, "subjects": {str(id): [slot_key, ...]}}
            Only teachers/subjects with at least one UNAVAILABLE slot appear in the result.
    """
    teacher_unavail = {}
    subject_unavail = {}
    seen_teachers = set()
    seen_subjects = set()

    for schedule in schedules or []:
        teacher = getattr(schedule, "teacher", None)
        if teacher is not None and schedule.teacher_id not in seen_teachers:
            seen_teachers.add(schedule.teacher_id)
            slots = [
                k
                for k, v in (teacher.time_preferences or {}).items()
                if v == TeacherTimePreferenceState.UNAVAILABLE
            ]
            if slots:
                teacher_unavail[str(schedule.teacher_id)] = slots

        subject = getattr(schedule, "subject", None)
        if subject is not None and schedule.subject_id not in seen_subjects:
            seen_subjects.add(schedule.subject_id)
            slots = [
                k
                for k, v in (subject.time_preferences or {}).items()
                if v == SubjectTimePreferenceState.UNAVAILABLE
            ]
            if slots:
                subject_unavail[str(schedule.subject_id)] = slots

    return {"teachers": teacher_unavail, "subjects": subject_unavail}


class ScheduleViewSet(TeamScopedAuditableModelViewSet):
    """CRUD and timetable management API for schedules.

    Export, generation option parsing, and move/swap helpers live in the
    views_export, views_generate and views_move modules respectively.
    """

    queryset = Schedule.objects.all().select_related(
        "teacher", "classroom", "group", "subject"
    )
    serializer_class = ScheduleSerializer
    EXPORT_ENTITY_CONFIG = {
        "teacher": {
            "label": "Profesor",
            "model": Teacher,
            "field": "teacher",
        },
        "group": {
            "label": "Curso",
            "model": Group,
            "field": "group",
        },
        "classroom": {
            "label": "Aula",
            "model": Classroom,
            "field": "classroom",
        },
    }

    @classmethod
    def _parse_id_list_param(cls, request, field_name):
        """Parse a query parameter that may contain a comma-separated or repeated list of IDs.
        Input: request - DRF Request; field_name - query parameter name
        Output: tuple (sorted_unique_ids, None) on success, or (None, Response) with HTTP 400
        """
        raw_values = []
        raw_single = request.query_params.get(field_name)
        if raw_single not in (None, ""):
            raw_values.extend(str(raw_single).split(","))

        for raw_value in request.query_params.getlist(field_name):
            if raw_value in (None, ""):
                continue
            raw_values.extend(str(raw_value).split(","))

        normalized = []
        for raw in raw_values:
            token = str(raw).strip()
            if not token:
                continue
            parsed, parse_error = parse_positive_int(token, field_name)
            if parse_error is not None:
                return None, parse_error
            normalized.append(parsed)

        return sorted(set(normalized)), None

    @classmethod
    def _parse_card_filters(cls, request):
        """Parse card-based filter parameters (group, teacher, classroom) from the request.
        Input: request - DRF Request with query params
        Output: tuple (filters_dict, None) on success, or (None, Response) with HTTP 400;
                filters_dict contains mode, filters (per entity type) and has_any_filter flag
        """
        card_specs = {
            "group": {"all_param": "group_all", "ids_param": "group_ids"},
            "teacher": {"all_param": "teacher_all", "ids_param": "teacher_ids"},
            "classroom": {
                "all_param": "classroom_all",
                "ids_param": "classroom_ids",
            },
        }

        filters = {}
        for entity_type, spec in card_specs.items():
            include_all, include_all_error = parse_bool_param(
                request.query_params.get(spec["all_param"]),
                spec["all_param"],
            )
            if include_all_error is not None:
                return None, include_all_error

            selected_ids, selected_ids_error = cls._parse_id_list_param(
                request,
                spec["ids_param"],
            )
            if selected_ids_error is not None:
                return None, selected_ids_error

            filters[entity_type] = {
                "include_all": include_all,
                "ids": selected_ids,
            }

        has_any_filter = any(
            value["include_all"] or value["ids"] for value in filters.values()
        )
        return {
            "mode": "cards",
            "filters": filters,
            "has_any_filter": has_any_filter,
        }, None

    @staticmethod
    def _filter_queryset_with_cards(queryset, filters):
        """Apply card-based entity filters to a Schedule queryset.
        Input: queryset - Schedule queryset; filters - dict from _parse_card_filters
        Output: filtered queryset; returns queryset.none() if no criteria are provided
        """
        card_to_field = {
            "group": "group",
            "teacher": "teacher",
            "classroom": "classroom",
        }

        criteria = Q(pk__in=[])
        has_criteria = False
        for entity_type, config in filters.items():
            field_name = card_to_field[entity_type]

            if config["include_all"]:
                criteria |= Q(**{f"{field_name}__isnull": False})
                has_criteria = True

            if config["ids"]:
                criteria |= Q(**{f"{field_name}_id__in": config["ids"]})
                has_criteria = True

        if not has_criteria:
            return queryset.none()

        return queryset.filter(criteria).distinct()

    @staticmethod
    def _resolve_source_queryset(queryset, source):
        """Filter a queryset by schedule source (generated or saved).
        Input: queryset - Schedule queryset; source - 'generated', 'saved' or 'all'
        Output: filtered queryset
        """
        if source == "generated":
            return queryset.filter(observations=AUTO_GENERATED_OBSERVATION)
        if source == "saved":
            return queryset.exclude(observations=AUTO_GENERATED_OBSERVATION)
        return queryset

    @staticmethod
    def _resolve_entity_filtered_queryset(queryset, entity_type, entity_id):
        """Filter a queryset to a specific entity (group, teacher, classroom or subject).
        Input: queryset - Schedule queryset; entity_type - field name to filter on;
               entity_id - integer PK of the entity
        Output: filtered queryset
        """
        if entity_type == "group":
            return queryset.filter(group_id=entity_id)
        if entity_type == "teacher":
            return queryset.filter(teacher_id=entity_id)
        if entity_type == "classroom":
            return queryset.filter(classroom_id=entity_id)
        if entity_type == "subject":
            return queryset.filter(subject_id=entity_id)
        return queryset

    @classmethod
    def _parse_export_params(cls, request):
        """Parse and validate all export-related query parameters from the request.
        Input: request - DRF Request with query params
        Output: tuple (params_dict, None) on success, or (None, Response) with HTTP 400;
                params_dict has keys: format, source, scope, entity_type, entity_id,
                saved_timetable_name and optionally card_filters
        """
        export_format = (
            (request.query_params.get("export_format") or "csv").strip().lower()
        )
        if export_format not in {"csv", "pdf"}:
            return None, Response(
                {"detail": "export_format must be one of: csv, pdf."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source = (request.query_params.get("source") or "all").strip().lower()
        if source not in {"all", "generated", "saved"}:
            return None, Response(
                {"detail": "source must be one of: all, generated, saved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_timetable_name = (
            request.query_params.get("saved_timetable_name") or ""
        ).strip()

        include_tc = request.query_params.get("include_tc", "0") == "1"

        if request.query_params.get("selection_mode") == "cards":
            card_filters, card_filter_error = cls._parse_card_filters(request)
            if card_filter_error is not None:
                return None, card_filter_error

            return {
                "format": export_format,
                "source": source,
                "scope": "cards",
                "card_filters": card_filters,
                "saved_timetable_name": saved_timetable_name,
                "include_tc": include_tc,
            }, None

        scope = (request.query_params.get("scope") or "all").strip().lower()
        if scope not in {"all", "entity"}:
            return None, Response(
                {"detail": "scope must be one of: all, entity."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entity_type = (request.query_params.get("entity_type") or "").strip().lower()
        entity_id = request.query_params.get("entity_id")

        if scope == "entity":
            if entity_type not in {"group", "teacher", "classroom", "subject"}:
                return None, Response(
                    {
                        "detail": (
                            "entity_type must be one of: group, teacher, classroom, "
                            "subject when scope=entity."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if entity_id in (None, ""):
                return None, Response(
                    {"detail": "entity_id is required when scope=entity."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            parsed_entity_id, entity_error = parse_positive_int(
                entity_id,
                "entity_id",
            )
            if entity_error is not None:
                return None, entity_error
            entity_id = parsed_entity_id
        else:
            entity_type = None
            entity_id = None

        return {
            "format": export_format,
            "source": source,
            "scope": scope,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "saved_timetable_name": saved_timetable_name,
            "include_tc": include_tc,
        }, None

    def _apply_export_queryset_filters(self, queryset, params, saved_name, request):
        if params["source"] == "generated":
            queryset = queryset.filter(users=request.user)
        elif params["source"] == "saved":
            if saved_name:
                queryset = queryset.filter(
                    observations=f"{SAVED_TIMETABLE_PREFIX}: {saved_name}"
                )
            else:
                queryset = queryset.filter(users=request.user)
        if params["scope"] == "entity":
            queryset = self._resolve_entity_filtered_queryset(
                queryset, params["entity_type"], params["entity_id"]
            )
        elif params["scope"] == "cards":
            queryset = self._filter_queryset_with_cards(
                queryset, params["card_filters"]["filters"]
            )
        return queryset

    def _fetch_tc_sessions_for_export(self, params, saved_name):
        from schedule.models import TCSession

        tc_qs = TCSession.objects.filter(team=self.get_active_team()).select_related(
            "teacher"
        )
        source = params["source"]
        if source == "generated":
            tc_qs = tc_qs.filter(observations="")
        elif source == "saved":
            if saved_name:
                tc_qs = tc_qs.filter(
                    observations=f"{SAVED_TIMETABLE_PREFIX}: {saved_name}"
                )
            else:
                tc_qs = tc_qs.filter(
                    observations__startswith=f"{SAVED_TIMETABLE_PREFIX}: "
                )
        return list(tc_qs.order_by("day", "start_time"))

    def export(self, request):
        """Export schedules as CSV, Excel or PDF.
        Input: request - DRF Request with export query params
        Output: HttpResponse with the exported file as an attachment
        """
        params, error_response = self._parse_export_params(request)
        if error_response is not None:
            return error_response

        saved_name = (params.get("saved_timetable_name") or "").strip()
        queryset = self.get_queryset().order_by("start_time", "id")
        queryset = self._resolve_source_queryset(queryset, params["source"])
        queryset = self._apply_export_queryset_filters(
            queryset, params, saved_name, request
        )

        include_tc = bool(params.get("include_tc"))
        card_filters = params.get("card_filters") or {}
        teacher_filter = (card_filters.get("filters") or {}).get("teacher") or {}
        has_teacher_cards = params.get("scope") == "cards" and (
            teacher_filter.get("include_all") or bool(teacher_filter.get("ids"))
        )

        tc_sessions = None
        if include_tc or has_teacher_cards:
            tc_sessions = self._fetch_tc_sessions_for_export(params, saved_name)

        saved_schedule_name = resolve_saved_schedule_name(params, queryset)
        units = build_export_units(
            queryset,
            params,
            active_team=self.get_active_team(),
            export_entity_config=self.EXPORT_ENTITY_CONFIG,
            tc_sessions=tc_sessions,
            add_tc_roster=include_tc,
        )
        filename = build_export_filename(params, saved_schedule_name)

        if params["format"] == "csv":
            if params.get("scope") == "cards":
                excel_filename = filename.rsplit(".", 1)[0] + ".xlsx"
                return build_excel_response(units, excel_filename)
            rows = build_export_rows(queryset)
            if tc_sessions:
                tc_rows = build_tc_export_rows(tc_sessions)
                rows = sorted(
                    rows + tc_rows,
                    key=lambda r: (_DAY_ORDER.get(r["day"], 99), r["start"]),
                )
            return build_csv_response_for_schedule(rows, filename)
        return build_pdf_units_response(units, filename)

    def generate(self, request):
        """Start an async schedule generation job and return its ID immediately.
        Input: request - DRF Request with optional seed and generation options in body
        Output: Response with job_id (HTTP 202); client polls generate_status for the result
        """
        from schedule.views_generate_job import run_generation_job

        actor = getattr(request.user, "email", "")
        active_team = self.get_active_team()
        raw_seed = request.data.get("seed")
        generation_options, options_error = parse_generation_options(request.data)
        if options_error is not None:
            raise ValidationAppError(
                "INVALID_GENERATION_OPTION",
                options_error.data.get("detail", "Invalid schedule generation option."),
            )

        if raw_seed in (None, ""):
            generation_seed = random.SystemRandom().randrange(1, 2**31 - 1)
        else:
            try:
                generation_seed = int(raw_seed)
            except (TypeError, ValueError):
                raise ValidationAppError(
                    "INVALID_INTEGER",
                    "seed must be an integer value.",
                    field_name="seed",
                    context={"field": "seed", "value": raw_seed},
                )

        job = ScheduleGenerationJob.objects.create(
            team=active_team,
            created_by=request.user,
            generation_options=generation_options,
        )

        thread = threading.Thread(
            target=run_generation_job,
            kwargs={
                "job_id": job.id,
                "actor_email": actor,
                "user_id": request.user.id,
                "team_id": active_team.id,
                "generation_seed": generation_seed,
                "generation_options": generation_options,
            },
            daemon=True,
        )
        thread.start()

        return Response({"job_id": str(job.id)}, status=status.HTTP_202_ACCEPTED)

    def generate_status(self, request, job_id=None):
        """Return the current status (and result when done) of a generation job.
        Input: request - DRF Request; job_id - UUID from the URL
        Output: Response with status field plus result or error when applicable (HTTP 200)
        """
        active_team = self.get_active_team()
        try:
            job = ScheduleGenerationJob.objects.get(id=job_id, team=active_team)
        except ScheduleGenerationJob.DoesNotExist:
            from rest_framework.exceptions import NotFound

            raise NotFound()

        # Detect stale jobs: RUNNING but the worker process died before completing
        if job.status == ScheduleGenerationJob.Status.RUNNING and job.started_at:
            timeout_minutes = (job.generation_options or {}).get("timeout_minutes") or 0
            stale_threshold_minutes = max(timeout_minutes, 5) + 10
            elapsed = (timezone.now() - job.started_at).total_seconds() / 60
            if elapsed > stale_threshold_minutes:
                job.status = ScheduleGenerationJob.Status.ERROR
                job.error_data = {
                    "detail": "La generación fue interrumpida inesperadamente.",
                    "_error": {
                        "code": "JOB_STALE",
                        "message": "Generation job stopped responding.",
                    },
                }
                job.completed_at = timezone.now()
                job.save(update_fields=["status", "error_data", "completed_at"])

        if job.status == ScheduleGenerationJob.Status.DONE:
            result = job.result_data or {}
            schedule_ids = result.get("schedule_ids", [])
            schedules = list(
                self.get_queryset()
                .filter(id__in=schedule_ids)
                .order_by("start_time", "id")
            )
            serialized = self.get_serializer(schedules, many=True)
            return Response(
                {
                    "status": job.status,
                    "result": {
                        "detail": "Schedule generated successfully.",
                        "seed": result.get("seed"),
                        "generation_options": result.get("generation_options"),
                        "optimization_is_optimal": result.get(
                            "optimization_is_optimal"
                        ),
                        "soft_score": result.get("soft_score"),
                        "schedules": serialized.data,
                        "generated_count": len(serialized.data),
                        "teacher_workloads": build_teacher_workloads(schedules),
                        "unavailability": build_unavailability_index(schedules),
                        "stage_windows": build_stage_windows_for_client(
                            getattr(active_team, "schedule_config", None)
                        ),
                        "tc_warnings": result.get("tc_warnings", []),
                    },
                }
            )

        if job.status == ScheduleGenerationJob.Status.ERROR:
            raw_error = job.error_data or {}
            nested = raw_error.get("_error") if isinstance(raw_error, dict) else None
            code = nested.get("code") if isinstance(nested, dict) else None
            if code == "INTERNAL_ERROR":
                safe_error = {
                    "detail": raw_error.get(
                        "detail",
                        "An unexpected error occurred during schedule generation.",
                    ),
                    "_error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Internal server error.",
                    },
                }
                return Response({"status": job.status, "error": safe_error})
            return Response({"status": job.status, "error": raw_error})

        return Response(
            {
                "status": job.status,
                "current_phase": job.current_phase,
                "started_at": job.started_at,
            }
        )

    def _saved_queryset(self):
        """Return a queryset of all saved (non-auto-generated) schedules for the active team.
        Output: Schedule queryset excluding auto-generated observations, scoped to the team
        """
        return self.get_queryset().exclude(observations=AUTO_GENERATED_OBSERVATION)

    def saved(self, request):
        """Return all saved schedules for the active team.
        Input: request - DRF Request
        Output: Response with count, results and teacher workloads (HTTP 200)
        """
        saved_queryset = self._saved_queryset().order_by("start_time", "id")
        saved_schedules = list(saved_queryset)
        serialized = self.get_serializer(saved_schedules, many=True)
        return Response(
            {
                "count": len(serialized.data),
                "results": serialized.data,
                "teacher_workloads": build_teacher_workloads(saved_schedules),
            },
            status=status.HTTP_200_OK,
        )

    def saved_summary(self, request):
        """Return a summary of saved timetable names for the current user.
        Input: request - DRF Request
        Output: Response with count and results (name + updated_at per timetable) (HTTP 200)
        """
        summary_queryset = (
            self._saved_queryset()
            .exclude(name__isnull=True)
            .exclude(name__exact="")
            .values("name")
            .annotate(updated_at=Max("updated_at"))
            .order_by("-updated_at", "name")
        )
        summary_items = list(summary_queryset)
        return Response(
            {
                "count": len(summary_items),
                "results": summary_items,
            },
            status=status.HTTP_200_OK,
        )

    def saved_detail(self, request):
        """Return all schedules for a specific saved timetable by name.
        Input: request - DRF Request with timetable_name query param
        Output: Response with count, results and teacher workloads (HTTP 200), or 400/404 on error
        """
        timetable_name = (request.query_params.get("timetable_name") or "").strip()
        if not timetable_name:
            return Response(
                {"detail": "timetable_name query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedules, error_response = self._fetch_saved_timetable_schedules(
            timetable_name=timetable_name,
            team=self.get_active_team(),
        )
        if error_response is not None:
            return error_response

        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "count": len(serialized.data),
                "results": serialized.data,
                "teacher_workloads": build_teacher_workloads(schedules),
                "unavailability": build_unavailability_index(schedules),
                "stage_windows": build_stage_windows_for_client(
                    getattr(self.get_active_team(), "schedule_config", None)
                ),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _parse_saved_timetable_name(payload):
        """Extract and validate the timetable_name field from a request payload.
        Input: payload - request data dict
        Output: tuple (timetable_name, None) on success, or (None, Response) with HTTP 400
        """
        timetable_name = (payload.get("timetable_name") or "").strip()
        if not timetable_name:
            return None, Response(
                {"timetable_name": "timetable_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return timetable_name, None

    @staticmethod
    def _fetch_saved_timetable_schedules(*, timetable_name, team):
        """Fetch all schedules belonging to a saved timetable by name.
        Input: timetable_name - saved timetable name; team - Team instance
        Output: tuple (schedules, None) on success, or (None, Response) with HTTP 404 if not found
        """
        saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
        schedules = list(
            Schedule.objects.select_related("teacher", "classroom", "group", "subject")
            .prefetch_related("users")
            .filter(
                observations=saved_observation,
                team=team,
            )
            .order_by("id")
        )
        if not schedules:
            return None, Response(
                {"detail": "Saved timetable not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return schedules, None

    @action(detail=False, methods=["post"], url_path="rename-saved-timetable")
    def rename_saved_timetable(self, request):
        """Rename a saved timetable by updating all its schedules' observations field.
        Input: request - DRF Request with old_name and new_name in body
        Output: Response with detail and updated_count (HTTP 200), or 400/404 on error
        """
        active_team = self.get_active_team()
        old_name = (request.data.get("old_name") or "").strip()
        if not old_name:
            return Response(
                {"old_name": "old_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        new_name = (request.data.get("new_name") or "").strip()
        if not new_name:
            return Response(
                {"new_name": "new_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self._saved_timetable_name_exists(
            timetable_name=old_name, team=active_team
        ):
            return Response(
                {"detail": "Saved timetable not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if self._saved_timetable_name_exists(timetable_name=new_name, team=active_team):
            return Response(
                {
                    "new_name": (
                        "Ya existe un horario guardado con ese nombre. "
                        "Usa otro nombre o elimina el horario anterior."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_obs = f"{SAVED_TIMETABLE_PREFIX}: {old_name}"
        new_obs = f"{SAVED_TIMETABLE_PREFIX}: {new_name}"
        updated_count = Schedule.objects.filter(
            observations=old_obs, team=active_team
        ).update(observations=new_obs)
        create_audit_entry(
            model=Schedule,
            entity_id=0,
            entity_name=new_name,
            action_type=AuditActionType.UPDATE,
            detail=(
                f'Se renombró el horario guardado "{old_name}" a "{new_name}" '
                f"({updated_count} sesiones actualizadas)."
            ),
            changed_fields=[
                {
                    "campo": "Nombre del horario",
                    "valor_anterior": old_name,
                    "valor_nuevo": new_name,
                }
            ],
            team=active_team,
        )
        return Response(
            {
                "detail": "Saved timetable renamed successfully.",
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="delete-saved-timetable")
    def delete_saved_timetable(self, request):
        """Delete a saved timetable and all its schedules.
        Input: request - DRF Request with timetable_name in body
        Output: Response with detail and deleted_count (HTTP 200), or 400/404 on error
        """
        timetable_name, error_response = self._parse_saved_timetable_name(request.data)
        if error_response is not None:
            return error_response

        schedules, error_response = self._fetch_saved_timetable_schedules(
            timetable_name=timetable_name,
            team=self.get_active_team(),
        )
        if error_response is not None:
            return error_response

        deleted_count = len(schedules)
        representative_schedule_id = schedules[0].pk
        with suppress_audit_events(("schedule", AuditActionType.DELETE)):
            for schedule in schedules:
                schedule.delete()

        create_audit_entry(
            model=Schedule,
            entity_id=representative_schedule_id,
            entity_name=timetable_name,
            action_type=AuditActionType.DELETE,
            detail=(
                f'Se eliminó el horario guardado "{timetable_name}" '
                f"con {deleted_count} sesiones."
            ),
            changed_fields=[
                {
                    "campo": "Sesiones eliminadas",
                    "valor_anterior": deleted_count,
                }
            ],
            team=self.get_active_team(),
        )
        return Response(
            {
                "detail": "Saved timetable deleted successfully.",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _parse_int_list(payload, field_name):
        """Parse a list of positive integers from a request payload field.
        Input: payload - request data dict; field_name - key to read
        Output: tuple (int_list, None) on success, or (None, Response) with HTTP 400 on failure
        """
        raw_values = payload.get(field_name) or []
        if field_name == "schedule_ids":
            if not isinstance(raw_values, list) or not raw_values:
                return None, Response(
                    {"detail": "schedule_ids must be a non-empty list."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif not isinstance(raw_values, list):
            return None, Response(
                {"detail": f"{field_name} must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            normalized_values = [int(value) for value in raw_values]
        except (TypeError, ValueError):
            return None, Response(
                {"detail": f"{field_name} must contain integer values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if any(value <= 0 for value in normalized_values):
            return None, Response(
                {field_name: f"{field_name} must contain positive integer values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(set(normalized_values)) != len(normalized_values):
            return None, Response(
                {field_name: f"{field_name} cannot contain duplicated values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return normalized_values, None

    @staticmethod
    def _ensure_request_user_in_user_ids(request_user_id, normalized_user_ids):
        """Ensure the requesting user's ID is included in the user ID list.
        Input: request_user_id - int PK of the current user;
               normalized_user_ids - mutable list of user PKs
        Output: normalized_user_ids with request_user_id added if absent
        """
        if request_user_id not in normalized_user_ids:
            normalized_user_ids.append(request_user_id)
        return normalized_user_ids

    @staticmethod
    def _fetch_target_users(normalized_user_ids, active_team):
        """Fetch and validate that all requested user IDs exist within the active team.
        Input: normalized_user_ids - list of user PKs; active_team - Team instance
        Output: tuple (user_list, None) on success, or (None, Response) with HTTP 400
        """
        requested_ids = set(normalized_user_ids)
        target_users = list(
            User.objects.filter(
                id__in=requested_ids,
                collaboration_teams=active_team,
            )
        )
        if len(target_users) != len(requested_ids):
            return None, Response(
                {
                    "detail": (
                        "Some user_ids do not exist or are outside the active team."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return target_users, None

    def _fetch_eligible_schedules(
        self, normalized_ids, request_user, actor_email, team
    ):
        """Fetch auto-generated schedules that are eligible to be saved.
        Input: normalized_ids - list of schedule PKs; request_user - User instance;
               actor_email - email of the actor; team - Team instance
        Output: tuple (schedules, None) on success, or (None, Response) with HTTP 400
        """
        requested_ids = set(normalized_ids)
        schedules = list(
            self.get_queryset()
            .prefetch_related("users")
            .filter(
                id__in=normalized_ids,
                users=request_user,
                created_by=actor_email,
                observations=AUTO_GENERATED_OBSERVATION,
                team=team,
            )
        )
        if len(schedules) != len(requested_ids):
            return None, Response(
                {
                    "detail": (
                        "Some schedules were not found or are not eligible to be saved "
                        "(must belong to current user and be auto-generated)."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return schedules, None

    @staticmethod
    def _persist_saved_schedules(
        *, schedules, timetable_name, actor_email, target_users
    ):
        """Update schedule records to mark them as a saved timetable.
        Input: schedules - list of Schedule instances; timetable_name - name to assign;
               actor_email - email for updated_by; target_users - User instances to associate
        Output: None; side-effect: saves each schedule and links target_users
        """
        if not schedules:
            return

        saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
        updated_at = timezone.now()
        schedule_ids = [schedule.id for schedule in schedules]
        target_user_ids = sorted({user.id for user in target_users})
        through_model = Schedule.users.through

        for schedule in schedules:
            schedule.name = timetable_name
            schedule.observations = saved_observation
            schedule.updated_by = actor_email
            schedule.updated_at = updated_at

        with transaction.atomic():
            Schedule.objects.filter(id__in=schedule_ids).update(
                name=timetable_name,
                observations=saved_observation,
                updated_by=actor_email,
                updated_at=updated_at,
            )

            existing_pairs = set(
                through_model.objects.filter(
                    schedule_id__in=schedule_ids,
                    user_id__in=target_user_ids,
                ).values_list("schedule_id", "user_id")
            )
            missing_pairs = [
                through_model(schedule_id=schedule_id, user_id=user_id)
                for schedule_id in schedule_ids
                for user_id in target_user_ids
                if (schedule_id, user_id) not in existing_pairs
            ]
            if missing_pairs:
                through_model.objects.bulk_create(missing_pairs, ignore_conflicts=True)

    @staticmethod
    def _saved_timetable_name_exists(*, timetable_name, team):
        """Check whether a saved timetable with the given name already exists for the team.
        Input: timetable_name - name to check; team - Team instance
        Output: True if a matching saved timetable exists, False otherwise
        """
        saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
        return Schedule.objects.filter(
            observations=saved_observation,
            team=team,
        ).exists()

    def save_generated(self, request):
        """Save a set of auto-generated schedules as a named timetable.
        Input: request - DRF Request with timetable_name, schedule_ids and user_ids in body
        Output: Response with detail, saved_count, schedules and teacher workloads (HTTP 200)
        """
        actor = getattr(request.user, "email", "")
        active_team = self.get_active_team()
        timetable_name = (request.data.get("timetable_name") or "").strip()

        if not timetable_name:
            return Response(
                {"timetable_name": "timetable_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self._saved_timetable_name_exists(
            timetable_name=timetable_name,
            team=active_team,
        ):
            return Response(
                {
                    "timetable_name": (
                        "A saved timetable with this name already exists. "
                        "Use another name or delete the previous one."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_ids, error_response = self._parse_int_list(
            request.data,
            "schedule_ids",
        )
        if error_response is not None:
            return error_response

        normalized_user_ids, error_response = self._parse_int_list(
            request.data,
            "user_ids",
        )
        if error_response is not None:
            return error_response

        normalized_user_ids = self._ensure_request_user_in_user_ids(
            request.user.id,
            normalized_user_ids,
        )

        if normalized_user_ids == [request.user.id]:
            target_users = [request.user]
        else:
            target_users, error_response = self._fetch_target_users(
                normalized_user_ids,
                active_team,
            )
            if error_response is not None:
                return error_response

        schedules, error_response = self._fetch_eligible_schedules(
            normalized_ids,
            request.user,
            actor,
            active_team,
        )
        if error_response is not None:
            return error_response

        self._persist_saved_schedules(
            schedules=schedules,
            timetable_name=timetable_name,
            actor_email=actor,
            target_users=target_users,
        )
        self._persist_saved_tc_sessions(timetable_name=timetable_name, team=active_team)

        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "detail": "Generated schedules saved successfully.",
                "saved_count": len(schedules),
                "schedules": serialized.data,
                "teacher_workloads": build_teacher_workloads(schedules),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _persist_saved_tc_sessions(*, timetable_name, team):
        """Copy draft TC sessions (observations="") to a saved timetable name.
        Deletes any existing TC sessions for that name first, then duplicates the drafts.
        Input: timetable_name - name of the saved timetable; team - CollaborationTeam instance
        Output: None
        """
        from schedule.constants import SAVED_TIMETABLE_PREFIX
        from schedule.models import TCSession

        saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
        TCSession.objects.filter(team=team, observations=saved_observation).delete()
        drafts = list(
            TCSession.objects.filter(team=team).exclude(
                observations__startswith=SAVED_TIMETABLE_PREFIX
            )
        )
        if drafts:
            for tc in drafts:
                tc.pk = None
                tc.name = timetable_name
                tc.observations = saved_observation
            TCSession.objects.bulk_create(drafts)

    def _resolve_timetable_scope_queryset(
        self,
        *,
        request_user,
        source_schedule,
        active_team,
    ):
        """Build a queryset scoped to the same timetable as the source schedule.
        Input: request_user - User instance; source_schedule - Schedule used as reference;
               active_team - Team instance
        Output: Schedule queryset for the timetable containing source_schedule
        """
        scoped_queryset = self.get_queryset().filter(
            users=request_user,
            team=active_team,
        )
        if source_schedule.observations == AUTO_GENERATED_OBSERVATION:
            return scoped_queryset.filter(
                observations=AUTO_GENERATED_OBSERVATION,
                created_by=source_schedule.created_by,
            )
        if source_schedule.observations.startswith(f"{SAVED_TIMETABLE_PREFIX}:"):
            return scoped_queryset.filter(observations=source_schedule.observations)
        return scoped_queryset.filter(
            name=source_schedule.name,
            observations=source_schedule.observations,
        )

    def _fetch_source_schedule_for_move(
        self, *, request_user, active_team, source_slot
    ):
        """Fetch and validate the source schedule for a move/swap operation.
        Input: request_user - User instance; active_team - Team instance;
               source_slot - parsed slot dict with schedule_id, day, start, end
        Output: tuple (schedule, None) on success, or (None, Response) with HTTP 404 or 409
        """
        source_schedule = (
            self.get_queryset()
            .filter(
                id=source_slot["schedule_id"],
                users=request_user,
                team=active_team,
            )
            .first()
        )
        if source_schedule is None:
            return None, Response(
                {"detail": "Source schedule not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        source_local_start = timezone.localtime(source_schedule.start_time)
        source_local_end = timezone.localtime(source_schedule.end_time)
        actual_source_day = WEEKDAY_TO_DAY_NAME.get(source_local_start.weekday())
        source_outdated = (
            actual_source_day != source_slot["day"]
            or source_local_start.strftime("%H:%M") != source_slot["start"]
            or source_local_end.strftime("%H:%M") != source_slot["end"]
        )
        if source_outdated:
            return None, Response(
                {
                    "detail": (
                        "La sesión de origen ya no coincide con los datos actuales. "
                        "Recarga y vuelve a intentarlo."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        return source_schedule, None

    @staticmethod
    def _move_no_changes_response(mode):
        """Build the standard no-changes response for a move/swap that would be a no-op.
        Input: mode - 'move' or 'swap'
        Output: Response with no_changes=True and empty affected lists (HTTP 200)
        """
        return Response(
            {
                "detail": "No changes were applied.",
                "mode": mode,
                "no_changes": True,
                "affected_schedules": [],
                "affected_slots": [],
                "teacher_workloads": [],
            },
            status=status.HTTP_200_OK,
        )

    def _resolve_move_scope(self, *, request_user, source_schedule, active_team):
        """Resolve the full timetable scope for a move/swap operation.
        Input: request_user - User instance; source_schedule - Schedule being moved;
               active_team - Team instance
        Output: tuple (scope_queryset, scope_schedules, scope_by_id, None) on success,
                or (None, None, None, Response) with HTTP 400 if source is out of scope
        """
        scope_queryset = self._resolve_timetable_scope_queryset(
            request_user=request_user,
            source_schedule=source_schedule,
            active_team=active_team,
        )
        scope_schedules = list(scope_queryset.order_by("id"))
        scope_by_id = {schedule.id: schedule for schedule in scope_schedules}
        if source_schedule.id not in scope_by_id:
            return (
                None,
                None,
                None,
                Response(
                    {"detail": "Source schedule is outside editable timetable scope."},
                    status=status.HTTP_400_BAD_REQUEST,
                ),
            )
        return scope_queryset, scope_schedules, scope_by_id, None

    def _resolve_swap_target_for_move(
        self,
        *,
        scope_queryset,
        scope_by_id,
        source_schedule,
        target_slot,
        target_start_dt,
        target_end_dt,
    ):
        """Resolve the swap target schedule from scope for a swap operation.
        Input: scope_queryset - Schedule queryset for this timetable;
               scope_by_id - dict {id: Schedule}; source_schedule - schedule being moved;
               target_slot - parsed slot dict; target_start_dt, target_end_dt - target times
        Output: tuple (target_schedule, None) on success, or (None, Response) with HTTP 400 or 409
        """
        target_schedule_id = target_slot["schedule_id"]
        if target_schedule_id is not None:
            target_schedule = scope_by_id.get(target_schedule_id)
            if target_schedule is None:
                return None, Response(
                    {
                        "detail": (
                            "El ID de sesión de destino no pertenece al mismo horario."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (
                target_schedule.start_time != target_start_dt
                or target_schedule.end_time != target_end_dt
            ):
                return None, Response(
                    {
                        "detail": (
                            "La sesión de destino ya no coincide con el hueco seleccionado. "
                            "Recarga y vuelve a intentarlo."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if (
                target_schedule.end_time - target_schedule.start_time
                != source_schedule.end_time - source_schedule.start_time
            ):
                return None, Response(
                    {
                        "detail": "No se puede intercambiar: las sesiones tienen distinta duración."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return target_schedule, None

        target_schedule = (
            scope_queryset.filter(start_time=target_start_dt, end_time=target_end_dt)
            .exclude(id=source_schedule.id)
            .order_by("id")
            .first()
        )
        if target_schedule is None:
            return None, Response(
                {
                    "detail": "El intercambio requiere una sesión en el hueco de destino."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            target_schedule.end_time - target_schedule.start_time
            != source_schedule.end_time - source_schedule.start_time
        ):
            return None, Response(
                {
                    "detail": "No se puede intercambiar: las sesiones tienen distinta duración."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return target_schedule, None

    @staticmethod
    def _apply_move_assignments(
        *,
        source_schedule,
        target_schedule,
        target_start_dt,
        target_end_dt,
        original_source_times,
        actor,
    ):
        """Persist the move or swap by updating start/end times of affected schedules.
        Input: source_schedule - Schedule to move; target_schedule - swap target or None;
               target_start_dt, target_end_dt - new times for source;
               original_source_times - (start, end) tuple of source before the change;
               actor - email string for updated_by
        Output: list of updated Schedule instances
        """
        affected_schedules = []
        with transaction.atomic():
            source_schedule.start_time = target_start_dt
            source_schedule.end_time = target_end_dt
            source_schedule.updated_by = actor
            source_schedule.save(
                update_fields=["start_time", "end_time", "updated_by", "updated_at"]
            )
            affected_schedules.append(source_schedule)

            if target_schedule is not None:
                target_schedule.start_time = original_source_times[0]
                target_schedule.end_time = original_source_times[1]
                target_schedule.updated_by = actor
                target_schedule.save(
                    update_fields=[
                        "start_time",
                        "end_time",
                        "updated_by",
                        "updated_at",
                    ]
                )
                affected_schedules.append(target_schedule)
        return affected_schedules

    def _parse_move_request_payload(self, payload):
        """Parse and validate the move/swap request payload.
        Input: payload - request data dict with mode, source_slot and target_slot
        Output: tuple (parsed_dict, None) on success, or (None, Response) with HTTP 400
        """
        mode, mode_error = normalize_move_mode(payload.get("mode"))
        if mode_error is not None:
            return None, mode_error

        source_slot, source_error = parse_move_slot(
            payload.get("source_slot"),
            "source_slot",
            require_schedule_id=True,
        )
        if source_error is not None:
            return None, source_error

        target_slot, target_error = parse_move_slot(
            payload.get("target_slot"),
            "target_slot",
            require_schedule_id=False,
        )
        if target_error is not None:
            return None, target_error

        return {
            "mode": mode,
            "source_slot": source_slot,
            "target_slot": target_slot,
        }, None

    def _resolve_target_schedule_for_mode(
        self,
        *,
        mode,
        scope_queryset,
        scope_by_id,
        source_schedule,
        target_slot,
        target_start_dt,
        target_end_dt,
    ):
        """Resolve the target schedule for swap mode, or return None for move mode.
        Input: mode - 'move' or 'swap'; scope_queryset - timetable queryset;
               scope_by_id - dict {id: Schedule}; source_schedule - source schedule;
               target_slot - parsed slot dict; target_start_dt, target_end_dt - target times
        Output: tuple (target_schedule, None) or (None, None) for move,
                or (None, Response) on swap resolution failure
        """
        if mode != "swap":
            return None, None

        return self._resolve_swap_target_for_move(
            scope_queryset=scope_queryset,
            scope_by_id=scope_by_id,
            source_schedule=source_schedule,
            target_slot=target_slot,
            target_start_dt=target_start_dt,
            target_end_dt=target_end_dt,
        )

    def move(self, request):
        """Move or swap a schedule session to a new time slot.
        Input: request - DRF Request with mode, source_slot and target_slot in body
        Output: Response with affected_schedules, affected_slots and teacher workloads (HTTP 200)
        """
        actor = getattr(request.user, "email", "")
        active_team = self.get_active_team()

        parsed_request, parsed_request_error = self._parse_move_request_payload(
            request.data
        )
        if parsed_request_error is not None:
            return parsed_request_error

        mode = parsed_request["mode"]
        source_slot = parsed_request["source_slot"]
        target_slot = parsed_request["target_slot"]

        source_schedule, source_schedule_error = self._fetch_source_schedule_for_move(
            request_user=request.user,
            active_team=active_team,
            source_slot=source_slot,
        )
        if source_schedule_error is not None:
            return source_schedule_error

        target_start_dt, target_end_dt = resolve_slot_datetimes_for_source_week(
            source_start=source_schedule.start_time,
            day_name=target_slot["day"],
            start_time=target_slot["start_time"],
            end_time=target_slot["end_time"],
        )

        (
            scope_queryset,
            scope_schedules,
            scope_by_id,
            scope_error,
        ) = self._resolve_move_scope(
            request_user=request.user,
            source_schedule=source_schedule,
            active_team=active_team,
        )
        if scope_error is not None:
            return scope_error

        target_schedule, target_schedule_error = self._resolve_target_schedule_for_mode(
            mode=mode,
            scope_queryset=scope_queryset,
            scope_by_id=scope_by_id,
            source_schedule=source_schedule,
            target_slot=target_slot,
            target_start_dt=target_start_dt,
            target_end_dt=target_end_dt,
        )
        if target_schedule_error is not None:
            return target_schedule_error

        if is_no_changes_move(
            mode=mode,
            source_schedule=source_schedule,
            target_schedule=target_schedule,
            target_start_dt=target_start_dt,
            target_end_dt=target_end_dt,
        ):
            return self._move_no_changes_response(mode)

        (
            assignments,
            changed_ids,
            original_source_times,
            original_target_times,
        ) = build_move_assignments(
            source_schedule=source_schedule,
            target_schedule=target_schedule,
            target_start_dt=target_start_dt,
            target_end_dt=target_end_dt,
        )

        validation_error = validate_minimal_move_constraints(
            scope_schedules=scope_schedules,
            assignments=assignments,
            changed_ids=changed_ids,
            slot_windows=parse_schedule_config_to_slot_windows(
                getattr(active_team, "schedule_config", None)
            ),
        )
        if validation_error is not None:
            return validation_error

        affected_schedules = self._apply_move_assignments(
            source_schedule=source_schedule,
            target_schedule=target_schedule,
            target_start_dt=target_start_dt,
            target_end_dt=target_end_dt,
            original_source_times=original_source_times,
            actor=actor,
        )

        unique_affected_slots = build_affected_slot_descriptors(
            original_source_times=original_source_times,
            target_start_dt=target_start_dt,
            target_end_dt=target_end_dt,
            original_target_times=original_target_times,
        )

        serialized = self.get_serializer(affected_schedules, many=True)
        return Response(
            {
                "detail": "Schedule change applied successfully.",
                "mode": "swap" if target_schedule is not None else "move",
                "no_changes": False,
                "affected_schedules": serialized.data,
                "affected_slots": unique_affected_slots,
                "teacher_workloads": build_teacher_workloads(scope_schedules),
            },
            status=status.HTTP_200_OK,
        )

    def _parse_analyze_params(self, request):
        """Parse and validate the analysis request parameters.
        Input: request - DRF Request with schedule_ids or source in body
        Output: tuple (schedule_ids, source); raises ValidationAppError on invalid params
        """
        schedule_ids = request.data.get("schedule_ids", [])
        source = (request.data.get("source") or "").strip().lower()

        if not (schedule_ids or source in {"generated", "saved"}):
            raise ValidationAppError(
                "INVALID_ANALYZE_PARAMS",
                "Se debe especificar schedule_ids o source (generated/saved).",
            )

        return schedule_ids, source

    def _get_schedules_to_analyze(self, queryset, schedule_ids, source):
        """Retrieve the schedules to analyse filtered by IDs or source.
        Input: queryset - base Schedule queryset; schedule_ids - list of specific IDs or empty;
               source - 'generated', 'saved', or empty string
        Output: list of Schedule instances; raises ValidationAppError if none found
        """
        if schedule_ids and isinstance(schedule_ids, list):
            schedules = list(queryset.filter(id__in=schedule_ids))
        elif source in {"generated", "saved"}:
            schedules = list(self._resolve_source_queryset(queryset, source))
        else:
            schedules = []

        if not schedules:
            raise ValidationAppError(
                "NO_SCHEDULES_FOUND",
                "No se encontraron horarios para analizar.",
            )

        return schedules

    def _parse_and_validate_analysis_request(self, request):
        """Parse the analysis request and return the resolved schedule list.
        Input: request - DRF Request
        Output: list of Schedule instances to analyse; raises ValidationAppError on failure
        """
        schedule_ids, source = self._parse_analyze_params(request)
        queryset = self.get_queryset()
        return self._get_schedules_to_analyze(queryset, schedule_ids, source)

    def _perform_defect_analysis(self, schedules):
        """Run the defect analyser on a list of schedules.
        Input: schedules - list of Schedule instances
        Output: list of defect dicts; raises ValidationAppError if analysis fails
        """
        try:
            from schedule.constants import SAVED_TIMETABLE_PREFIX
            from schedule.models import TCSession

            team = schedules[0].team if schedules else None
            if not team:
                tc_sessions = []
            else:
                first_obs = (schedules[0].observations or "") if schedules else ""
                if first_obs.startswith(SAVED_TIMETABLE_PREFIX):
                    tc_sessions = list(
                        TCSession.objects.filter(
                            team=team, observations=first_obs
                        ).select_related("teacher")
                    )
                else:
                    tc_sessions = list(
                        TCSession.objects.filter(
                            team=team, observations=""
                        ).select_related("teacher")
                    )
            return ScheduleEvaluator.analyze_schedules(
                schedules, tc_sessions=tc_sessions
            )
        except Exception as exc:
            logger.exception("Error analyzing schedules: %s", str(exc))
            raise ValidationAppError(
                "ANALYSIS_ERROR",
                f"Error al analizar el horario: {str(exc)}",
            )

    @action(detail=False, methods=["post"], url_path="analyze")
    def analyze(self, request):
        """Analyse a set of schedules for defects.
        Input: request - DRF Request with schedule_ids or source in body
        Output: Response with count and defects list (HTTP 200)
        """
        schedules = self._parse_and_validate_analysis_request(request)
        defects = self._perform_defect_analysis(schedules)

        return Response(
            {"count": len(defects), "defects": defects},
            status=status.HTTP_200_OK,
        )
