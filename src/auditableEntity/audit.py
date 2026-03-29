from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from auditableEntity.models import AuditActionType, AuditEntry

AUDITABLE_MODEL_LABELS = frozenset(
    {
        "teacher.Teacher",
        "classroom.Classroom",
        "group.Group",
        "subject.Subject",
        "schedule.Schedule",
        "user.User",
    }
)
AUDITABLE_ENTITY_TYPES = frozenset(
    {
        "teacher",
        "classroom",
        "group",
        "subject",
        "schedule",
        "user",
    }
)
AUDIT_EXCLUDED_FIELD_NAMES = frozenset(
    {
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "password",
        "last_login",
        "date_joined",
        "is_staff",
        "is_superuser",
        "first_name",
        "last_name",
        "is_active",
    }
)
ENTITY_LABELS = {
    "teacher": "Profesor",
    "classroom": "Aula",
    "group": "Grupo",
    "subject": "Asignatura",
    "schedule": "Horario",
    "user": "Usuario",
}
ENTITY_PHRASES = {
    "teacher": "el profesor",
    "classroom": "el aula",
    "group": "el grupo",
    "subject": "la asignatura",
    "schedule": "el horario",
    "user": "el usuario",
}
FIELD_LABELS = {
    "name": "Nombre",
    "family_name": "Apellidos",
    "email": "Correo",
    "role": "Rol",
    "is_enabled": "Activo",
    "max_weekly_hours": "Máximo de horas semanales",
    "working_hours": "Horas de trabajo",
    "time_preferences": "Preferencias horarias",
    "is_shared": "Compartida",
    "stage": "Etapa",
    "weekly_hours": "Horas semanales",
    "duration": "Duración",
    "preferred_time_slot": "Franja horaria preferida",
    "type": "Tipo",
    "teacher": "Profesor",
    "group": "Grupo",
    "allowed_classrooms": "Aulas permitidas",
    "observations": "Observaciones",
    "start_time": "Hora de inicio",
    "end_time": "Hora de fin",
    "classroom": "Aula",
    "subject": "Asignatura",
    "users": "Usuarios",
}
_AUDIT_ACTOR = ContextVar("audit_actor", default={"user": None})
_AUDIT_SUPPRESSION = ContextVar("audit_suppression", default=frozenset())


def get_entity_type(model):
    return model._meta.model_name


def get_entity_label(model):
    return ENTITY_LABELS.get(get_entity_type(model), model.__name__)


def get_entity_phrase(model):
    return ENTITY_PHRASES.get(get_entity_type(model), get_entity_label(model))


def get_field_label(field_name):
    return FIELD_LABELS.get(field_name, field_name.replace("_", " ").capitalize())


def get_user_display_name(user):
    if user is None:
        return ""

    full_name_getter = getattr(user, "get_full_name", None)
    if callable(full_name_getter):
        full_name = full_name_getter().strip()
        if full_name:
            return full_name[:255]

    name = getattr(user, "name", "")
    if isinstance(name, str) and name.strip():
        return name.strip()[:255]

    return ""


def get_instance_name(instance):
    if instance is None:
        return ""

    user_name = get_user_display_name(instance)
    if user_name:
        return user_name

    candidate = getattr(instance, "name", "")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()[:255]

    try:
        rendered = str(instance).strip()
    except Exception:
        rendered = ""
    return rendered[:255]


def _serialize_scalar(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "Si" if value else "No"
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, list):
        return [_serialize_scalar(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _serialize_scalar(item)
            for key, item in value.items()
        }
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def _serialize_field_value(instance, field):
    if field.is_relation and field.many_to_one:
        related_instance = getattr(instance, field.name, None)
        return get_instance_name(related_instance) or None

    display_getter = getattr(instance, f"get_{field.name}_display", None)
    if callable(display_getter):
        return _serialize_scalar(display_getter())

    return _serialize_scalar(getattr(instance, field.name))


def snapshot_instance(instance):
    snapshot = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in AUDIT_EXCLUDED_FIELD_NAMES:
            continue
        value = _serialize_field_value(instance, field)
        snapshot[field.name] = value
    return snapshot


def build_create_changed_fields(after_snapshot):
    return [
        {
            "campo": get_field_label(field_name),
            "valor_nuevo": value,
        }
        for field_name, value in after_snapshot.items()
        if value not in (None, "", [], {})
    ]


def build_update_changed_fields(before_snapshot, after_snapshot):
    changes = []
    for field_name, new_value in after_snapshot.items():
        old_value = before_snapshot.get(field_name)
        if old_value == new_value:
            continue
        changes.append(
            {
                "campo": get_field_label(field_name),
                "valor_anterior": old_value,
                "valor_nuevo": new_value,
            }
        )
    return changes


def build_delete_changed_fields(before_snapshot):
    if before_snapshot.get("name"):
        return [
            {
                "campo": get_field_label("name"),
                "valor_anterior": before_snapshot.get("name"),
            }
        ]
    return []


def build_m2m_changed_fields(*, field_name, before_values, after_values):
    return [
        {
            "campo": get_field_label(field_name),
            "valor_anterior": before_values,
            "valor_nuevo": after_values,
        }
    ]


def get_current_actor():
    actor = _AUDIT_ACTOR.get()
    return actor.get("user")


def is_audit_suppressed(*, model, action_type):
    return (get_entity_type(model), action_type) in _AUDIT_SUPPRESSION.get()


@contextmanager
def audit_actor_context(*, user=None):
    token = _AUDIT_ACTOR.set(
        {
            "user": user if getattr(user, "is_authenticated", False) else None,
        }
    )
    try:
        yield
    finally:
        _AUDIT_ACTOR.reset(token)


@contextmanager
def suppress_audit_events(*rules):
    token = _AUDIT_SUPPRESSION.set(_AUDIT_SUPPRESSION.get().union(rules))
    try:
        yield
    finally:
        _AUDIT_SUPPRESSION.reset(token)


def build_action_detail(*, action_type, model, entity_name, changed_fields=None):
    entity_phrase = get_entity_phrase(model)
    safe_name = entity_name or "sin nombre"
    changed_fields = changed_fields or []

    if action_type == AuditActionType.CREATE:
        return f'Se creó {entity_phrase} "{safe_name}".'
    if action_type == AuditActionType.DELETE:
        return f'Se eliminó {entity_phrase} "{safe_name}".'
    if changed_fields:
        changed_names = ", ".join(change["campo"] for change in changed_fields)
        return (
            f'Se modificó {entity_phrase} "{safe_name}". '
            f"Campos modificados: {changed_names}."
        )
    return f'Se modificó {entity_phrase} "{safe_name}".'


def build_m2m_detail(*, model, entity_name, field_name):
    entity_phrase = get_entity_phrase(model)
    safe_name = entity_name or "sin nombre"
    return (
        f'Se modificó {entity_phrase} "{safe_name}". '
        f'Se actualizó el campo {get_field_label(field_name)}.'
    )


def create_audit_entry(
    *,
    model,
    entity_id,
    entity_name,
    action_type,
    detail,
    changed_fields=None,
):
    actor = get_current_actor()

    return AuditEntry.objects.create(
        entity_type=get_entity_type(model),
        entity_id=entity_id,
        entity_name=(entity_name or "")[:255],
        action_type=action_type,
        detail=detail,
        changed_fields=changed_fields or [],
        actor=actor,
        actor_name=get_user_display_name(actor),
    )
