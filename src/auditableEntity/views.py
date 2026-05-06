"""
Read-only API endpoints for filtering, listing, and exporting audit entries.
"""

from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import pagination, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from auditableEntity.audit import (
    AUDITABLE_ENTITY_TYPES,
    ENTITY_LABELS,
    format_changed_fields_for_export,
    get_action_label,
)
from auditableEntity.models import AuditActionType, AuditEntry
from auditableEntity.serializers import AuditEntrySerializer
from common.export_utils import (
    REPORTLAB_AVAILABLE,
    build_csv_response,
    build_table_pdf_response,
    sanitize_filename_stem,
)
from common.tenancy import get_active_team
from user.models import User

AUDIT_ENTITY_FILTER_CHOICES = (
    "schedule",
    "teacher",
    "classroom",
    "group",
    "subject",
    "user",
    "collaborationteam",
    "horario",
    "profesor",
    "aula",
    "grupo",
    "asignatura",
    "usuario",
    "configuracion",
    "configuración",
)
AUDIT_ACTION_FILTER_CHOICES = (
    "CREATE",
    "UPDATE",
    "DELETE",
    "creación",
    "creacion",
    "modificación",
    "modificacion",
    "borrado",
)
AUDIT_EXPORT_OPTIONAL_HEADERS = ["Fecha", "Usuario", "Elemento", "Acción"]
AUDIT_EXPORT_FIXED_HEADERS = ["Resumen", "Detalle"]
AUDIT_EXPORT_HEADERS = AUDIT_EXPORT_OPTIONAL_HEADERS + AUDIT_EXPORT_FIXED_HEADERS


class AuditPagination(pagination.PageNumberPagination):
    """Pagination for audit history lists shown in the dashboard."""

    page_size = 7
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for team-scoped audit history."""

    queryset = AuditEntry.objects.select_related("actor").all()
    serializer_class = AuditEntrySerializer
    pagination_class = AuditPagination
    permission_classes = [permissions.IsAuthenticated]
    ENTITY_FILTER_ALIASES = {
        "teacher": "teacher",
        "profesor": "teacher",
        "classroom": "classroom",
        "aula": "classroom",
        "group": "group",
        "grupo": "group",
        "subject": "subject",
        "asignatura": "subject",
        "schedule": "schedule",
        "horario": "schedule",
        "user": "user",
        "usuario": "user",
        "collaborationteam": "collaborationteam",
        "configuracion": "collaborationteam",
        "configuración": "collaborationteam",
    }
    ACTION_FILTER_ALIASES = {
        "create": "CREATE",
        "creación": "CREATE",
        "creacion": "CREATE",
        "update": "UPDATE",
        "modificación": "UPDATE",
        "modificacion": "UPDATE",
        "delete": "DELETE",
        "borrado": "DELETE",
    }

    @staticmethod
    def _parse_positive_int(raw_value, field_name):
        """Parse a positive integer from a query parameter value.
        Input: raw_value - raw string from query params; field_name - param name for error messages
        Output: int positive integer value
        """
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {field_name: "Debe ser un numero entero positivo."}
            ) from exc

        if value <= 0:
            raise ValidationError({field_name: "Debe ser un numero entero positivo."})
        return value

    @staticmethod
    def _normalize_datetime(raw_value, *, field_name, end_of_day=False):
        """Normalize an ISO date or datetime string into a timezone-aware datetime.
        Input: raw_value - str ISO date or datetime, or None; field_name - param name for errors;
               end_of_day - if True, use time.max for date-only inputs
        Output: timezone-aware datetime, or None if raw_value is empty
        """
        if raw_value in (None, ""):
            return None

        parsed_datetime = parse_datetime(str(raw_value))
        if parsed_datetime is not None:
            if timezone.is_naive(parsed_datetime):
                parsed_datetime = timezone.make_aware(
                    parsed_datetime,
                    timezone.get_current_timezone(),
                )
            return parsed_datetime

        parsed_date = parse_date(str(raw_value))
        if parsed_date is not None:
            base_time = time.max if end_of_day else time.min
            parsed_datetime = datetime.combine(parsed_date, base_time)
            return timezone.make_aware(parsed_datetime, timezone.get_current_timezone())

        raise ValidationError(
            {field_name: "Debe ser una fecha u hora valida en formato ISO."}
        )

    @staticmethod
    def _invalid_choice_error(field_name, allowed_values):
        """Build a standardized validation error for filter choice parameters.
        Input: field_name - query param name; allowed_values - iterable of valid choice strings
        Output: ValidationError with the field name and allowed values listed
        """
        allowed_text = ", ".join(allowed_values)
        return ValidationError({field_name: f"Debe ser uno de: {allowed_text}."})

    def _resolve_entity_type_filter(self, params):
        """Resolve and validate the entity type filter from query params.
        Input: params - dict-like query params (e.g. request.query_params)
        Output: str normalized entity_type, or empty string if not provided
        """
        raw_entity_type = (params.get("tipo_entidad") or "").strip().lower()
        entity_type = self.ENTITY_FILTER_ALIASES.get(raw_entity_type, "")
        if not entity_type and raw_entity_type:
            raise self._invalid_choice_error(
                "tipo_entidad",
                AUDIT_ENTITY_FILTER_CHOICES,
            )
        if entity_type and entity_type not in AUDITABLE_ENTITY_TYPES:
            raise self._invalid_choice_error(
                "tipo_entidad",
                sorted(AUDITABLE_ENTITY_TYPES),
            )
        return entity_type

    def _resolve_action_type_filter(self, params):
        """Resolve and validate the action type filter from query params.
        Input: params - dict-like query params
        Output: str AuditActionType value, or empty string if not provided
        """
        raw_action_type = (params.get("tipo_accion") or "").strip().lower()
        action_type = self.ACTION_FILTER_ALIASES.get(raw_action_type, "")
        if not action_type and raw_action_type:
            raise self._invalid_choice_error(
                "tipo_accion",
                AUDIT_ACTION_FILTER_CHOICES,
            )
        if action_type and action_type not in set(AuditActionType.values):
            raise self._invalid_choice_error("tipo_accion", AuditActionType.values)
        return action_type

    def _resolve_actor_id_filter(self, params):
        """Resolve and validate the actor filter from query params.
        Input: params - dict-like query params
        Output: int actor user id, or None if not provided
        """
        raw_actor_id = params.get("usuario_id")
        if raw_actor_id in (None, ""):
            return None

        actor_id = self._parse_positive_int(raw_actor_id, "usuario_id")
        if actor_id not in self._allowed_actor_ids():
            raise ValidationError(
                {"usuario_id": "Debes seleccionar un usuario válido de tu equipo."}
            )
        return actor_id

    def _resolve_date_filters(self, params):
        """Resolve the optional date range filters from query params.
        Input: params - dict-like query params
        Output: tuple of (date_from, date_to) as timezone-aware datetimes or None
        """
        date_from = self._normalize_datetime(
            params.get("fecha_desde"),
            field_name="fecha_desde",
        )
        date_to = self._normalize_datetime(
            params.get("fecha_hasta"),
            field_name="fecha_hasta",
            end_of_day=True,
        )
        return date_from, date_to

    @staticmethod
    def _filter_by_exact_value(queryset, field_name, value):
        """Filter a queryset by an exact value only when the value is present.
        Input: queryset - Django QuerySet; field_name - ORM field path; value - filter value or empty
        Output: filtered QuerySet, or original queryset if value is absent
        """
        if value in (None, ""):
            return queryset
        return queryset.filter(**{field_name: value})

    @staticmethod
    def _filter_by_icontains(queryset, field_name, value):
        """Filter a queryset by a case-insensitive contains lookup when provided.
        Input: queryset - Django QuerySet; field_name - ORM field path; value - search string
        Output: filtered QuerySet, or original queryset if value is falsy
        """
        if not value:
            return queryset
        return queryset.filter(**{f"{field_name}__icontains": value})

    @staticmethod
    def _filter_by_actor_id(queryset, actor_id):
        """Filter a queryset by actor id only when the filter is present.
        Input: queryset - Django QuerySet; actor_id - int id or None
        Output: filtered QuerySet, or original queryset if actor_id is None
        """
        if actor_id is None:
            return queryset
        return queryset.filter(actor_id=actor_id)

    @staticmethod
    def _filter_by_datetime_bounds(queryset, *, date_from, date_to):
        """Apply optional lower and upper datetime bounds to a queryset.
        Input: queryset - Django QuerySet; date_from - lower bound datetime or None;
               date_to - upper bound datetime or None
        Output: QuerySet with occurred_at bounds applied
        """
        if date_from is not None:
            queryset = queryset.filter(occurred_at__gte=date_from)
        if date_to is not None:
            queryset = queryset.filter(occurred_at__lte=date_to)
        return queryset

    def _apply_filters(self, queryset, params):
        """Apply all supported query parameter filters to the audit queryset.
        Input: queryset - base AuditEntry QuerySet; params - dict-like query params
        Output: filtered QuerySet with entity_type, action_type, actor, name, and date filters applied
        """
        entity_type = self._resolve_entity_type_filter(params)
        action_type = self._resolve_action_type_filter(params)
        actor_id = self._resolve_actor_id_filter(params)
        actor_name = (params.get("usuario") or "").strip()
        date_from, date_to = self._resolve_date_filters(params)

        queryset = self._filter_by_exact_value(queryset, "entity_type", entity_type)
        queryset = self._filter_by_exact_value(queryset, "action_type", action_type)
        queryset = self._filter_by_actor_id(queryset, actor_id)
        queryset = self._filter_by_icontains(queryset, "actor_name", actor_name)
        return self._filter_by_datetime_bounds(
            queryset,
            date_from=date_from,
            date_to=date_to,
        )

    def get_queryset(self):
        """Return the active-team audit queryset with any requested filters applied.
        Input: None (uses self.request implicitly)
        Output: QuerySet of AuditEntry filtered to active team, ordered by -occurred_at, -id
        """
        active_team = get_active_team(self.request)
        queryset = super().get_queryset().filter(team=active_team)
        queryset = self._apply_filters(queryset, self.request.query_params)
        return queryset.order_by("-occurred_at", "-id")

    def _allowed_actor_ids(self):
        """Return the set of user ids that can be used in the actor filter.
        Input: None (uses self.request implicitly via _allowed_users_queryset)
        Output: set of int user ids belonging to the active team
        """
        return set(self._allowed_users_queryset().values_list("id", flat=True))

    def _allowed_users_queryset(self):
        """Return the ordered queryset of users available in the current team.
        Input: None (uses self.request implicitly)
        Output: QuerySet of User instances filtered to active team, ordered by name and id
        """
        active_team = get_active_team(self.request)
        return (
            User.objects.filter(
                collaboration_teams=active_team,
            )
            .distinct()
            .order_by("name", "family_name", "id")
        )

    @staticmethod
    def _parse_export_format(raw_value):
        """Parse and validate the requested export format.
        Input: raw_value - str from query params, or None
        Output: str 'csv' or 'pdf'
        """
        export_format = (raw_value or "csv").strip().lower()
        if export_format not in {"csv", "pdf"}:
            raise ValidationError({"export_format": "Debe ser uno de: csv, pdf."})
        return export_format

    @staticmethod
    def _build_export_filename(export_format):
        """Build the timestamped filename used by audit exports.
        Input: export_format - str 'csv' or 'pdf'
        Output: str filename with timestamp and extension (e.g. 'orarioo_audit_20240101_120000.csv')
        """
        stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        stem = sanitize_filename_stem(f"orarioo_audit_{stamp}", "orarioo_audit")
        return f"{stem}.{export_format}"

    @staticmethod
    def _build_export_rows(queryset, *, for_csv=False, optional_indices=None):
        """Serialize audit entries into row values for CSV or PDF export.
        Input: queryset - AuditEntry QuerySet; for_csv - if True, prefix date cell with quote;
               optional_indices - indices into AUDIT_EXPORT_OPTIONAL_HEADERS to include (None = all)
        Output: list of lists with [selected optional cols...] + [Resumen, Detalle]
        """
        all_optional_indices = list(range(len(AUDIT_EXPORT_OPTIONAL_HEADERS)))
        indices = (
            optional_indices if optional_indices is not None else all_optional_indices
        )
        rows = []
        for entry in queryset:
            occurred_at = timezone.localtime(entry.occurred_at).strftime(
                "%d/%m/%Y %H:%M"
            )
            optional_cells = [
                f"'{occurred_at}" if for_csv else occurred_at,
                entry.actor_name or "-",
                ENTITY_LABELS.get(entry.entity_type, entry.entity_type),
                get_action_label(entry.action_type),
            ]
            row = [optional_cells[i] for i in indices] + [
                entry.detail or "-",
                format_changed_fields_for_export(entry.changed_fields) or "-",
            ]
            rows.append(row)
        return rows

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """Export the filtered audit history as CSV or PDF.
        Input: request - HTTP GET with optional export_format, columns, and filter query params
        Output: HttpResponse with CSV or PDF content and appropriate Content-Disposition header
        """
        export_format = self._parse_export_format(
            request.query_params.get("export_format")
        )
        queryset = self.get_queryset()
        filename = self._build_export_filename(export_format)

        requested_columns = request.query_params.getlist("columns")
        if requested_columns:
            valid = {
                col for col in requested_columns if col in AUDIT_EXPORT_OPTIONAL_HEADERS
            }
            optional_headers = [
                col for col in AUDIT_EXPORT_OPTIONAL_HEADERS if col in valid
            ]
            optional_indices = [
                AUDIT_EXPORT_OPTIONAL_HEADERS.index(col) for col in optional_headers
            ]
        else:
            optional_headers = []
            optional_indices = []
        headers = optional_headers + AUDIT_EXPORT_FIXED_HEADERS

        if export_format == "csv":
            rows = self._build_export_rows(
                queryset, for_csv=True, optional_indices=optional_indices
            )
            return build_csv_response(headers, rows, filename)

        if not REPORTLAB_AVAILABLE:
            raise ValidationError(
                {
                    "detail": (
                        "La exportación PDF no está disponible porque reportlab "
                        "no está instalado."
                    )
                }
            )
        return build_table_pdf_response(
            headers=headers,
            rows=self._build_export_rows(queryset, optional_indices=optional_indices),
            filename=filename,
            title_text="Historial de auditoría",
        )

    @action(detail=False, methods=["get"], url_path="filter-users")
    def filter_users(self, request):
        """Return the selectable users for the audit filter dropdown.
        Input: request - HTTP GET request (team inferred from request.user)
        Output: JSON Response with list of dicts containing 'id' and 'nombre' for each team user
        """
        users = [
            {
                "id": user.id,
                "nombre": user.get_full_name() or user.name or f"Usuario {user.id}",
            }
            for user in self._allowed_users_queryset()
        ]
        return Response(users)
