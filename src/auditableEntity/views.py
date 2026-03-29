from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError

from auditableEntity.audit import AUDITABLE_ENTITY_TYPES
from auditableEntity.models import AuditActionType, AuditEntry
from auditableEntity.serializers import AuditEntrySerializer
from user.models import CollaborationTeam


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
        "creación": "CREATE",
        "update": "UPDATE",
        "modificación": "UPDATE",
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

    def get_queryset(self):
        queryset = super().get_queryset().filter(actor_id__in=self._allowed_actor_ids())
        params = self.request.query_params

        raw_entity_type = (params.get("tipo_entidad") or "").strip().lower()
        entity_type = self.ENTITY_FILTER_ALIASES.get(raw_entity_type, "")
        if entity_type:
            if entity_type not in AUDITABLE_ENTITY_TYPES:
                raise ValidationError(
                    {
                        "tipo_entidad": (
                            "Debe ser uno de: "
                            f"{', '.join(sorted(AUDITABLE_ENTITY_TYPES))}."
                        )
                    }
                )
            queryset = queryset.filter(entity_type=entity_type)
        elif raw_entity_type:
            raise ValidationError(
                {
                    "tipo_entidad": (
                        "Debe ser uno de: schedule, teacher, classroom, group, "
                        "subject, user, horario, profesor, aula, grupo, "
                        "asignatura, usuario."
                    )
                }
            )

        raw_action_type = (params.get("tipo_accion") or "").strip().lower()
        action_type = self.ACTION_FILTER_ALIASES.get(raw_action_type, "")
        if action_type:
            if action_type not in set(AuditActionType.values):
                raise ValidationError(
                    {
                        "tipo_accion": (
                            "Debe ser uno de: " f"{', '.join(AuditActionType.values)}."
                        )
                    }
                )
            queryset = queryset.filter(action_type=action_type)
        elif raw_action_type:
            raise ValidationError(
                {
                    "tipo_accion": (
                        "Debe ser uno de: CREATE, UPDATE, DELETE, "
                        "creación, modificación, borrado."
                    )
                }
            )

        date_from = self._normalize_datetime(
            params.get("fecha_desde"),
            field_name="fecha_desde",
        )
        if date_from is not None:
            queryset = queryset.filter(occurred_at__gte=date_from)

        date_to = self._normalize_datetime(
            params.get("fecha_hasta"),
            field_name="fecha_hasta",
            end_of_day=True,
        )
        if date_to is not None:
            queryset = queryset.filter(occurred_at__lte=date_to)

        return queryset.order_by("-occurred_at", "-id")

    def _allowed_actor_ids(self):
        current_user = self.request.user
        allowed_ids = {current_user.id}
        team_ids = CollaborationTeam.objects.filter(members=current_user).values_list(
            "id",
            flat=True,
        )
        teammate_ids = CollaborationTeam.objects.filter(id__in=team_ids).values_list(
            "members__id",
            flat=True,
        )
        allowed_ids.update(teammate_ids)
        return allowed_ids
