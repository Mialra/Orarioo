from datetime import datetime, time

from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from auditableEntity.audit import (
    AUDITABLE_ENTITY_TYPES,
    ENTITY_LABELS,
    format_changed_fields_for_export,
)
from auditableEntity.models import AuditActionType, AuditEntry
from auditableEntity.serializers import AuditEntrySerializer
from common.export_utils import (
    REPORTLAB_AVAILABLE,
    build_csv_response,
    build_table_pdf_response,
    sanitize_filename_stem,
)
from user.models import CollaborationTeam, User


class AuditEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEntry.objects.select_related("actor").all()
    serializer_class = AuditEntrySerializer
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
    }
    ACTION_FILTER_ALIASES = {
        "create": "CREATE",
        "creaci\u00f3n": "CREATE",
        "creacion": "CREATE",
        "update": "UPDATE",
        "modificaci\u00f3n": "UPDATE",
        "modificacion": "UPDATE",
        "delete": "DELETE",
        "borrado": "DELETE",
    }

    @staticmethod
    def _parse_positive_int(raw_value, field_name):
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

    def _resolve_entity_type_filter(self, params):
        raw_entity_type = (params.get("tipo_entidad") or "").strip().lower()
        entity_type = self.ENTITY_FILTER_ALIASES.get(raw_entity_type, "")
        if not entity_type and raw_entity_type:
            raise ValidationError(
                {
                    "tipo_entidad": (
                        "Debe ser uno de: schedule, teacher, classroom, group, "
                        "subject, user, horario, profesor, aula, grupo, "
                        "asignatura, usuario."
                    )
                }
            )
        if entity_type and entity_type not in AUDITABLE_ENTITY_TYPES:
            raise ValidationError(
                {
                    "tipo_entidad": (
                        "Debe ser uno de: "
                        f"{', '.join(sorted(AUDITABLE_ENTITY_TYPES))}."
                    )
                }
            )
        return entity_type

    def _resolve_action_type_filter(self, params):
        raw_action_type = (params.get("tipo_accion") or "").strip().lower()
        action_type = self.ACTION_FILTER_ALIASES.get(raw_action_type, "")
        if not action_type and raw_action_type:
            raise ValidationError(
                {
                    "tipo_accion": (
                        "Debe ser uno de: CREATE, UPDATE, DELETE, "
                        "creaci\u00f3n, creacion, modificaci\u00f3n, modificacion, borrado."
                    )
                }
            )
        if action_type and action_type not in set(AuditActionType.values):
            raise ValidationError(
                {
                    "tipo_accion": (
                        "Debe ser uno de: " f"{', '.join(AuditActionType.values)}."
                    )
                }
            )
        return action_type

    def _resolve_actor_id_filter(self, params):
        raw_actor_id = params.get("usuario_id")
        if raw_actor_id in (None, ""):
            return None

        actor_id = self._parse_positive_int(raw_actor_id, "usuario_id")
        if actor_id not in self._allowed_actor_ids():
            raise ValidationError(
                {"usuario_id": "Debes seleccionar un usuario v\u00e1lido de tu equipo."}
            )
        return actor_id

    def _resolve_date_filters(self, params):
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

    def _apply_filters(self, queryset, params):
        entity_type = self._resolve_entity_type_filter(params)
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)

        action_type = self._resolve_action_type_filter(params)
        if action_type:
            queryset = queryset.filter(action_type=action_type)

        actor_id = self._resolve_actor_id_filter(params)
        if actor_id is not None:
            queryset = queryset.filter(actor_id=actor_id)

        actor_name = (params.get("usuario") or "").strip()
        if actor_name:
            queryset = queryset.filter(actor_name__icontains=actor_name)

        date_from, date_to = self._resolve_date_filters(params)
        if date_from is not None:
            queryset = queryset.filter(occurred_at__gte=date_from)
        if date_to is not None:
            queryset = queryset.filter(occurred_at__lte=date_to)

        return queryset

    def get_queryset(self):
        queryset = super().get_queryset().filter(actor_id__in=self._allowed_actor_ids())
        queryset = self._apply_filters(queryset, self.request.query_params)
        return queryset.order_by("-occurred_at", "-id")

    def _allowed_actor_ids(self):
        return set(self._allowed_users_queryset().values_list("id", flat=True))

    def _allowed_users_queryset(self):
        current_user = self.request.user
        team_ids = CollaborationTeam.objects.filter(members=current_user).values_list(
            "id",
            flat=True,
        )
        return (
            User.objects.filter(
                models.Q(id=current_user.id)
                | models.Q(collaboration_teams__id__in=team_ids)
            )
            .distinct()
            .order_by("name", "family_name", "id")
        )

    @staticmethod
    def _parse_export_format(raw_value):
        export_format = (raw_value or "csv").strip().lower()
        if export_format not in {"csv", "pdf"}:
            raise ValidationError({"export_format": "Debe ser uno de: csv, pdf."})
        return export_format

    @staticmethod
    def _build_export_filename(export_format):
        stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        stem = sanitize_filename_stem(f"orarioo_audit_{stamp}", "orarioo_audit")
        return f"{stem}.{export_format}"

    @staticmethod
    def _build_export_rows(queryset, *, for_csv=False):
        action_labels = {
            AuditActionType.CREATE: "Creaci\u00f3n",
            AuditActionType.UPDATE: "Modificaci\u00f3n",
            AuditActionType.DELETE: "Borrado",
        }
        rows = []
        for entry in queryset:
            occurred_at = timezone.localtime(entry.occurred_at).strftime(
                "%d/%m/%Y %H:%M"
            )
            rows.append(
                [
                    f"'{occurred_at}" if for_csv else occurred_at,
                    entry.actor_name or "-",
                    ENTITY_LABELS.get(entry.entity_type, entry.entity_type),
                    entry.entity_name or "-",
                    action_labels.get(entry.action_type, entry.action_type),
                    entry.detail or "-",
                    format_changed_fields_for_export(entry.changed_fields) or "-",
                ]
            )
        return rows

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        export_format = self._parse_export_format(
            request.query_params.get("export_format")
        )
        queryset = self.get_queryset()
        headers = [
            "Fecha",
            "Usuario",
            "Entidad",
            "Nombre",
            "Acci\u00f3n",
            "Resumen",
            "Detalle",
        ]
        filename = self._build_export_filename(export_format)

        if export_format == "csv":
            rows = self._build_export_rows(queryset, for_csv=True)
            return build_csv_response(headers, rows, filename)

        if not REPORTLAB_AVAILABLE:
            raise ValidationError(
                {
                    "detail": (
                        "La exportaci\u00f3n PDF no est\u00e1 disponible porque reportlab "
                        "no est\u00e1 instalado."
                    )
                }
            )
        return build_table_pdf_response(
            headers=headers,
            rows=self._build_export_rows(queryset),
            filename=filename,
            title_text="Historial de auditor\u00eda",
        )

    @action(detail=False, methods=["get"], url_path="filter-users")
    def filter_users(self, request):
        users = [
            {
                "id": user.id,
                "nombre": user.get_full_name() or user.name or f"Usuario {user.id}",
            }
            for user in self._allowed_users_queryset()
        ]
        return Response(users)
