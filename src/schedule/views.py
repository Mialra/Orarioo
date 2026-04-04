import logging
import random
import re
from io import BytesIO

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from auditableEntity.audit import create_audit_entry, suppress_audit_events
from auditableEntity.models import AuditActionType
from classroom.models import Classroom
from common.drf import TeamScopedAuditableModelViewSet
from common.export_utils import build_csv_response, sanitize_filename_stem
from group.models import Group
from schedule.algorithm import BasicScheduleGenerator, ScheduleGenerationError
from schedule.algorithm.generator import ScheduleReplanner
from schedule.constants import AUTO_GENERATED_OBSERVATION, SAVED_TIMETABLE_PREFIX
from schedule.models import Schedule
from schedule.serializers import ScheduleSerializer
from teacher.models import Teacher
from user.models import User

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class ScheduleViewSet(TeamScopedAuditableModelViewSet):
    """CRUD API for schedules."""

    GENERATION_FAILED_DETAIL = (
        "Unable to generate schedule with the current input constraints."
    )
    DEFAULT_GENERATION_OPTIONS = {
        "recess_supervisors_preschool": 0,
        "recess_supervisors_primary": 0,
    }

    queryset = Schedule.objects.all().select_related(
        "teacher", "classroom", "group", "subject"
    )
    serializer_class = ScheduleSerializer
    EXPORT_ENTITY_ORDER = ["teacher", "classroom", "group"]
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
    STAGE_TC_BREAK_SLOTS = {
        "preschool": [("10:30", "11:00"), ("13:30", "14:00")],
        "primary": [("11:30", "12:00")],
        "secondary": [("11:00", "11:30")],
    }

    @staticmethod
    def _parse_positive_int(raw_value, field_name):
        if raw_value in (None, ""):
            return None, None
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            return None, Response(
                {"detail": f"{field_name} must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if parsed <= 0:
            return None, Response(
                {"detail": f"{field_name} must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return parsed, None

    @staticmethod
    def _resolve_source_queryset(queryset, source):
        if source == "generated":
            return queryset.filter(observations=AUTO_GENERATED_OBSERVATION)
        if source == "saved":
            return queryset.exclude(observations=AUTO_GENERATED_OBSERVATION)
        return queryset

    @staticmethod
    def _resolve_entity_filtered_queryset(queryset, entity_type, entity_id):
        if entity_type == "group":
            return queryset.filter(group_id=entity_id)
        if entity_type == "teacher":
            return queryset.filter(teacher_id=entity_id)
        if entity_type == "classroom":
            return queryset.filter(classroom_id=entity_id)
        if entity_type == "subject":
            return queryset.filter(subject_id=entity_id)
        return queryset

    @staticmethod
    def _parse_bool_param(raw_value, field_name):
        if raw_value in (None, ""):
            return False, None

        normalized = str(raw_value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True, None
        if normalized in {"0", "false", "no", "off"}:
            return False, None

        return False, Response(
            {
                "detail": (
                    f"{field_name} must be a boolean value "
                    "(true/false, 1/0, yes/no)."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    @classmethod
    def _parse_id_list_param(cls, request, field_name):
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
            parsed, parse_error = cls._parse_positive_int(token, field_name)
            if parse_error is not None:
                return None, parse_error
            normalized.append(parsed)

        return sorted(set(normalized)), None

    @classmethod
    def _parse_card_filters(cls, request):
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
            include_all, include_all_error = cls._parse_bool_param(
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

    @classmethod
    def _parse_export_params(cls, request):
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
            parsed_entity_id, entity_error = cls._parse_positive_int(
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
        }, None

    @classmethod
    def _resolve_saved_schedule_name(cls, params, queryset):
        explicit_name = (params.get("saved_timetable_name") or "").strip()
        if explicit_name:
            return explicit_name

        if params.get("source") != "saved":
            return ""

        names = list(
            queryset.exclude(name__isnull=True)
            .exclude(name__exact="")
            .values_list("name", flat=True)
            .distinct()[:1]
        )
        if names:
            return names[0]
        return ""

    @classmethod
    def _build_export_filename(cls, params, saved_schedule_name=""):
        if params["source"] == "saved" and saved_schedule_name:
            stem = sanitize_filename_stem(saved_schedule_name, "orarioo_saved_schedule")
        else:
            date_token = timezone.now().strftime("%Y%m%d_%H%M%S")
            stem = f"orarioo_generated_schedule_{date_token}"
        return f"{stem}.{params['format']}"

    @classmethod
    def _build_export_rows(cls, schedules):
        rows = []
        for schedule in schedules:
            rows.append(
                {
                    "subject": schedule.subject.name if schedule.subject else "",
                    "teacher": schedule.teacher.name if schedule.teacher else "",
                    "group": schedule.group.name if schedule.group else "",
                    "classroom": schedule.classroom.name if schedule.classroom else "",
                }
            )
        return rows

    @classmethod
    def _build_export_units(cls, queryset, params, active_team):
        units = []
        if params.get("scope") != "cards":
            rows = cls._build_export_rows(queryset)
            units.append(
                {
                    "entity_type": "mixed",
                    "header": "",
                    "rows": rows,
                    "schedules": list(queryset),
                }
            )
            return units

        filters = params["card_filters"]["filters"]
        for entity_type in cls.EXPORT_ENTITY_ORDER:
            config = cls.EXPORT_ENTITY_CONFIG[entity_type]
            field_name = config["field"]
            entity_filter = filters[entity_type]

            selected_ids = []
            if entity_filter["include_all"]:
                selected_ids.extend(
                    list(
                        queryset.exclude(**{f"{field_name}_id__isnull": True})
                        .values_list(f"{field_name}_id", flat=True)
                        .distinct()
                    )
                )
            selected_ids.extend(entity_filter["ids"])

            selected_ids = sorted(set(selected_ids))
            if not selected_ids:
                continue

            model_cls = config["model"]
            name_map = {
                obj.id: obj.name
                for obj in model_cls.objects.filter(
                    id__in=selected_ids,
                    team=active_team,
                ).only("id", "name")
            }

            for object_id in selected_ids:
                object_name = name_map.get(object_id, f"{config['label']} {object_id}")
                object_queryset = queryset.filter(
                    **{f"{field_name}_id": object_id}
                ).order_by("start_time", "id")
                units.append(
                    {
                        "entity_type": entity_type,
                        "header": f"{config['label']} {object_name}",
                        "rows": cls._build_export_rows(object_queryset),
                        "schedules": list(object_queryset),
                    }
                )

        return units

    @staticmethod
    def _build_csv_response(rows, filename):
        header = [
            "Asignatura",
            "Profesor",
            "Curso",
            "Aula",
        ]
        return build_csv_response(
            header,
            [
                [
                    row["subject"],
                    row["teacher"],
                    row["group"],
                    row["classroom"],
                ]
                for row in rows
            ],
            filename,
        )

    @classmethod
    @staticmethod
    def _make_unique_sheet_title(base_title, used_titles):
        """Generate a unique Excel sheet title (max 31 chars)."""
        safe = re.sub(r"[\\/*?:\[\]]+", "_", base_title).strip() or "Horario"
        safe = safe[:31]
        if safe not in used_titles:
            used_titles.add(safe)
            return safe
        counter = 2
        while True:
            suffix = f"_{counter}"
            candidate = f"{safe[:31 - len(suffix)]}{suffix}"
            if candidate not in used_titles:
                used_titles.add(candidate)
                return candidate
            counter += 1

    @staticmethod
    def _populate_excel_sheet(sheet, headers, rows):
        """Add headers and rows to an Excel sheet."""
        sheet.append(headers)
        for row in rows:
            sheet.append(
                [
                    row["subject"],
                    row["teacher"],
                    row["group"],
                    row["classroom"],
                ]
            )

    @classmethod
    def _build_excel_workbook(cls, units):
        """Create Excel workbook with multiple sheets from export units."""
        from openpyxl import Workbook

        workbook = Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)

        headers = ["Asignatura", "Profesor", "Curso", "Aula"]
        used_titles = set()

        if not units:
            sheet = workbook.create_sheet(title="Sin datos")
            sheet.append(headers)
        else:
            for index, unit in enumerate(units, start=1):
                base_title = unit["header"] or f"Horario {index}"
                sheet_title = cls._make_unique_sheet_title(base_title, used_titles)
                sheet = workbook.create_sheet(title=sheet_title)
                cls._populate_excel_sheet(sheet, headers, unit["rows"])

        return workbook

    @classmethod
    def _build_excel_response(cls, units, filename):
        """Build Excel HTTP response with multiple sheets or fallback to CSV."""
        try:
            workbook = cls._build_excel_workbook(units)
        except ImportError:
            merged_rows = []
            for unit in units:
                merged_rows.extend(unit["rows"])
            fallback_filename = re.sub(r"\.xlsx$", ".csv", filename)
            return cls._build_csv_response(merged_rows, fallback_filename)

        buffer = BytesIO()
        workbook.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument." "spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @staticmethod
    def _normalize_stage(stage_value):
        """Normalize stage name to standard form."""
        value = (stage_value or "").strip().lower()
        if "preschool" in value or "infantil" in value:
            return "preschool"
        if "primary" in value or "primaria" in value:
            return "primary"
        if "secondary" in value or "eso" in value:
            return "secondary"
        return value

    @classmethod
    @staticmethod
    def _describe_schedule(schedule):
        """Get display name for a schedule's subject."""
        return schedule.subject.name if schedule.subject else "-"

    @classmethod
    def _collect_slots_and_content(cls, schedules):
        """Collect all time slots and cell content from schedules."""
        weekday_to_name = {
            0: "Lunes",
            1: "Martes",
            2: "Miércoles",
            3: "Jueves",
            4: "Viernes",
        }
        slot_keys = []
        cell_content = {}
        day_stage_map = {}

        for schedule in schedules:
            local_start = timezone.localtime(schedule.start_time)
            local_end = timezone.localtime(schedule.end_time)
            weekday = local_start.weekday()
            if weekday not in weekday_to_name:
                continue

            day_name = weekday_to_name[weekday]
            slot = (local_start.strftime("%H:%M"), local_end.strftime("%H:%M"))
            if slot not in slot_keys:
                slot_keys.append(slot)

            key = (day_name, slot)
            cell_content.setdefault(key, []).append(cls._describe_schedule(schedule))

            # Track stages for TC breaks
            normalized_stage = cls._normalize_stage(
                getattr(schedule.group, "stage", "") if schedule.group else ""
            )
            if normalized_stage in cls.STAGE_TC_BREAK_SLOTS:
                day_stage_map.setdefault(day_name, set()).add(normalized_stage)

        return slot_keys, cell_content, day_stage_map

    @classmethod
    def _inject_tc_breaks(cls, slot_keys, cell_content, day_stage_map):
        """Add TC break slots to timetable for teacher schedules."""
        for day_name, stages in day_stage_map.items():
            for stage in stages:
                for tc_slot in cls.STAGE_TC_BREAK_SLOTS[stage]:
                    if tc_slot not in slot_keys:
                        slot_keys.append(tc_slot)
                    key = (day_name, tc_slot)
                    cell_content.setdefault(key, []).append("Trabajo de Centro")

    @classmethod
    def _build_timetable_rows(cls, slot_keys, cell_content):
        """Build table rows from slots and content."""
        days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        table_data = [["Hora", *days]]
        for slot in slot_keys:
            row = [f"{slot[0]} - {slot[1]}"]
            for day in days:
                entries = cell_content.get((day, slot), [])
                row.append("\n\n".join(entries))
            table_data.append(row)
        return table_data

    @classmethod
    def _build_timetable_table_data(cls, schedules, entity_type):
        """Build table data for timetable PDF/export."""
        slot_keys, cell_content, day_stage_map = cls._collect_slots_and_content(
            schedules
        )

        if entity_type == "teacher":
            cls._inject_tc_breaks(slot_keys, cell_content, day_stage_map)

        slot_keys.sort()
        if not slot_keys:
            return [
                ["Hora", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
                ["Sin sesiones", "", "", "", "", ""],
            ]

        return cls._build_timetable_rows(slot_keys, cell_content)

    @staticmethod
    def _build_pdf_response(rows, filename, title_text=""):
        if not REPORTLAB_AVAILABLE:
            return Response(
                {
                    "detail": (
                        "PDF export is unavailable because reportlab is not installed. "
                        "Install reportlab to enable PDF exports."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24,
        )

        del rows
        del title_text
        story = []
        document.build(story)

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @classmethod
    def _build_pdf_units_response(cls, units, filename):
        if not REPORTLAB_AVAILABLE:
            return Response(
                {
                    "detail": (
                        "PDF export is unavailable because reportlab is not installed. "
                        "Install reportlab to enable PDF exports."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24,
        )

        styles = getSampleStyleSheet()
        story = []

        for index, unit in enumerate(units):
            if index > 0:
                story.append(PageBreak())

            if unit["header"]:
                story.extend(
                    [
                        Paragraph(f"<b>{unit['header']}</b>", styles["Title"]),
                        Spacer(1, 10),
                    ]
                )

            table_data = cls._build_timetable_table_data(
                unit["schedules"], unit["entity_type"]
            )

            available_width = document.width
            time_col_width = available_width * 0.15
            day_col_width = (available_width - time_col_width) / 5
            col_widths = [time_col_width, *([day_col_width] * 5)]

            table = Table(table_data, repeatRows=1, colWidths=col_widths)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7ecfb")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b7bfd4")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(table)

        document.build(story)

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def export(self, request):
        params, error_response = self._parse_export_params(request)
        if error_response is not None:
            return error_response

        queryset = self.get_queryset().order_by("start_time", "id")
        queryset = self._resolve_source_queryset(queryset, params["source"])
        if params["scope"] == "entity":
            queryset = self._resolve_entity_filtered_queryset(
                queryset,
                params["entity_type"],
                params["entity_id"],
            )
        elif params["scope"] == "cards":
            queryset = self._filter_queryset_with_cards(
                queryset,
                params["card_filters"]["filters"],
            )

        saved_schedule_name = self._resolve_saved_schedule_name(params, queryset)
        units = self._build_export_units(
            queryset,
            params,
            active_team=self.get_active_team(),
        )
        rows = self._build_export_rows(queryset)
        filename = self._build_export_filename(params, saved_schedule_name)

        if params["format"] == "csv":
            if params.get("scope") == "cards":
                excel_filename = filename.rsplit(".", 1)[0] + ".xlsx"
                return self._build_excel_response(units, excel_filename)
            return self._build_csv_response(rows, filename)
        return self._build_pdf_units_response(units, filename)

    @staticmethod
    def _parse_generation_int(payload, field_name, *, min_value, max_value):
        raw_value = payload.get(field_name)
        if raw_value in (None, ""):
            return None, None
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return None, Response(
                {"detail": f"{field_name} must be an integer value."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if value < min_value or value > max_value:
            return None, Response(
                {
                    "detail": (
                        f"{field_name} must be between {min_value} and {max_value}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return value, None

    @classmethod
    def _parse_base_generation_int_options(cls, payload, options):
        int_fields = {
            "recess_supervisors_preschool": (0, 20),
            "recess_supervisors_primary": (0, 20),
        }

        for field_name, bounds in int_fields.items():
            parsed, error_response = cls._parse_generation_int(
                payload,
                field_name,
                min_value=bounds[0],
                max_value=bounds[1],
            )
            if error_response is not None:
                return error_response
            if parsed is not None:
                options[field_name] = parsed
        return None

    @classmethod
    def _parse_generation_options(cls, payload):
        options = dict(cls.DEFAULT_GENERATION_OPTIONS)
        base_options_error = cls._parse_base_generation_int_options(
            payload,
            options,
        )
        if base_options_error is not None:
            return None, base_options_error

        return options, None

    def generate(self, request):
        actor = getattr(request.user, "email", "")
        active_team = self.get_active_team()
        raw_seed = request.data.get("seed")
        generation_options, options_error = self._parse_generation_options(request.data)
        if options_error is not None:
            return options_error

        if raw_seed in (None, ""):
            generation_seed = random.SystemRandom().randrange(1, 2**31 - 1)
        else:
            try:
                generation_seed = int(raw_seed)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "seed must be an integer value."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            schedules = BasicScheduleGenerator.generate(
                actor_email=actor,
                user=request.user,
                team=active_team,
                random_seed=generation_seed,
                generation_options=generation_options,
            )
        except ScheduleGenerationError as exc:
            logger.warning(
                "Schedule generation rejected: actor=%s, reason=%s",
                actor,
                exc,
            )
            return Response(
                {
                    "detail": self.GENERATION_FAILED_DETAIL,
                    "error_code": "schedule_generation_failed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "detail": "Schedule generated successfully.",
                "seed": generation_seed,
                "generation_options": generation_options,
                "schedules": serialized.data,
                "generated_count": len(serialized.data),
            },
            status=status.HTTP_201_CREATED,
        )

    def saved(self, request):
        saved_queryset = (
            self.get_queryset()
            .exclude(observations=AUTO_GENERATED_OBSERVATION)
            .filter(users=request.user)
            .order_by("start_time", "id")
        )
        serialized = self.get_serializer(saved_queryset, many=True)
        return Response(
            {
                "count": len(serialized.data),
                "results": serialized.data,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _parse_saved_timetable_name(payload):
        timetable_name = (payload.get("timetable_name") or "").strip()
        if not timetable_name:
            return None, Response(
                {"timetable_name": "timetable_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return timetable_name, None

    @staticmethod
    def _fetch_saved_timetable_schedules(*, request_user, timetable_name, team):
        saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
        schedules = list(
            Schedule.objects.filter(
                users=request_user,
                observations=saved_observation,
                team=team,
            ).order_by("id")
        )
        if not schedules:
            return None, Response(
                {"detail": "Saved timetable not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return schedules, None

    @action(detail=False, methods=["post"], url_path="delete-saved-timetable")
    def delete_saved_timetable(self, request):
        timetable_name, error_response = self._parse_saved_timetable_name(request.data)
        if error_response is not None:
            return error_response

        schedules, error_response = self._fetch_saved_timetable_schedules(
            request_user=request.user,
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
                f'Se elimino el horario guardado "{timetable_name}" '
                f"con {deleted_count} sesiones."
            ),
            changed_fields=[
                {
                    "campo": "Sesiones eliminadas",
                    "valor_anterior": deleted_count,
                }
            ],
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
        if request_user_id not in normalized_user_ids:
            normalized_user_ids.append(request_user_id)
        return normalized_user_ids

    @staticmethod
    def _fetch_target_users(normalized_user_ids, active_team):
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

    @staticmethod
    def _fetch_eligible_schedules(normalized_ids, request_user, actor_email, team):
        requested_ids = set(normalized_ids)
        schedules = list(
            Schedule.objects.filter(
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
        saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
        for schedule in schedules:
            schedule.name = timetable_name
            schedule.observations = saved_observation
            schedule.updated_by = actor_email
            schedule.save(
                update_fields=["name", "observations", "updated_by", "updated_at"]
            )
            schedule.users.add(*target_users)

    def save_generated(self, request):
        actor = getattr(request.user, "email", "")
        active_team = self.get_active_team()
        timetable_name = (request.data.get("timetable_name") or "").strip()

        if not timetable_name:
            return Response(
                {"timetable_name": "timetable_name is required."},
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

        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "detail": "Generated schedules saved successfully.",
                "saved_count": len(schedules),
                "schedules": serialized.data,
            },
            status=status.HTTP_200_OK,
        )

    def apply_manual_change(self, request):
        """Apply a manual session-to-slot change and replan the entire schedule."""
        actor = getattr(request.user, "email", "")

        schedule_id = request.data.get("schedule_id")
        new_slot_index = request.data.get("new_slot_index")

        # Validate inputs
        if schedule_id is None:
            return Response(
                {"detail": "schedule_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_slot_index is None:
            return Response(
                {"detail": "new_slot_index is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            schedule_id = int(schedule_id)
            new_slot_index = int(new_slot_index)
        except (TypeError, ValueError):
            return Response(
                {"detail": "schedule_id and new_slot_index must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if schedule_id <= 0:
            return Response(
                {"schedule_id": "schedule_id must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_slot_index < 0:
            return Response(
                {"new_slot_index": "new_slot_index must be zero or greater."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_schedules = ScheduleReplanner.replan_with_manual_change(
                user=request.user,
                team=self.get_active_team(),
                schedule_to_move_id=schedule_id,
                new_slot_index=new_slot_index,
                actor_email=actor,
            )
        except ScheduleGenerationError:
            logger.warning(
                "ScheduleGenerationError while applying manual change: "
                "schedule_id=%s, new_slot_index=%s, actor=%s",
                schedule_id,
                new_slot_index,
                actor,
            )
            return Response(
                {"detail": "Failed to replan schedule with manual change."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serialized = self.get_serializer(new_schedules, many=True)
        return Response(
            {
                "detail": "Schedule replanned with manual change successfully.",
                "schedules": serialized.data,
                "generated_count": len(serialized.data),
            },
            status=status.HTTP_200_OK,
        )
