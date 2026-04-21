"""
Audit helpers for snapshotting entities, formatting changes, and creating entries.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, time
from decimal import Decimal
from itertools import chain
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
ACTION_LABELS = {
    AuditActionType.CREATE: "Creación",
    AuditActionType.UPDATE: "Modificación",
    AuditActionType.DELETE: "Borrado",
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
DISPLAY_VALUE_TRANSLATIONS = {
    "Preschool": "Infantil",
    "Primary": "Primaria",
    "Secondary": "Secundaria",
    "Normal": "Normal",
    "TC": "TC",
}
PREFERENCE_GROUPS = (
    ("PREFER_YES", "Preferidas"),
    ("AVAILABLE", "Disponibles"),
    ("PREFER_NO", "Poco preferidas"),
    ("UNAVAILABLE", "No disponibles"),
)
PREFERENCE_DAY_NAMES = {
    "MON": "Lunes",
    "TUE": "Martes",
    "WED": "Miércoles",
    "THU": "Jueves",
    "FRI": "Viernes",
}
_AUDIT_ACTOR = ContextVar("audit_actor", default={"user": None})
_AUDIT_SUPPRESSION = ContextVar("audit_suppression", default=frozenset())


def get_entity_type(model):
    """Return the normalized entity type stored in audit records for a model class.
    Input: model - a Django model class
    Output: str model_name (e.g. 'teacher', 'classroom')
    """
    return model._meta.model_name


def get_entity_label(model):
    """Return the Spanish display label for a model class.
    Input: model - a Django model class
    Output: str Spanish label (e.g. 'Profesor'), or model.__name__ if not found
    """
    return ENTITY_LABELS.get(get_entity_type(model), model.__name__)


def get_action_label(action_type):
    """Return the Spanish display label for an audit action.
    Input: action_type - an AuditActionType value string
    Output: str Spanish label (e.g. 'Creación'), or action_type if not found
    """
    return ACTION_LABELS.get(action_type, action_type)


def get_entity_phrase(model):
    """Return the phrase used in audit detail sentences for a model class.
    Input: model - a Django model class
    Output: str phrase (e.g. 'el profesor'), or entity label as fallback
    """
    return ENTITY_PHRASES.get(get_entity_type(model), get_entity_label(model))


def get_field_label(field_name):
    """Return the Spanish display label for an audited field name.
    Input: field_name - str field name (e.g. 'name', 'weekly_hours')
    Output: str Spanish label, or capitalized field_name with underscores replaced
    """
    return FIELD_LABELS.get(field_name, field_name.replace("_", " ").capitalize())


def get_user_display_name(user):
    """Return the best available short display name for a user-like object.
    Input: user - a User instance or None
    Output: str display name up to 255 chars, or empty string if unavailable
    """
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
    """Return the best available human-readable name for any model instance.
    Input: instance - any model instance or None
    Output: str name up to 255 chars; tries get_full_name, name attr, then str()
    """
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
    """Convert Python values into JSON-safe audit payload values.
    Input: value - any Python value (bool, datetime, Decimal, UUID, list, dict, etc.)
    Output: JSON-serializable scalar, list, or dict
    """
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
        return {str(key): _serialize_scalar(item) for key, item in value.items()}
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def _serialize_field_value(instance, field):
    """Serialize one model field from an instance into an audit snapshot value.
    Input: instance - a model instance; field - a concrete Django field descriptor
    Output: JSON-safe value representing the field's current value
    """
    if field.is_relation and field.many_to_one:
        related_instance = getattr(instance, field.name, None)
        return get_instance_name(related_instance) or None

    display_getter = getattr(instance, f"get_{field.name}_display", None)
    if callable(display_getter):
        return _serialize_scalar(display_getter())

    return _serialize_scalar(getattr(instance, field.name))


def snapshot_instance(instance):
    """Capture the auditable concrete-field state of an instance.
    Input: instance - a model instance
    Output: dict mapping field names to JSON-safe serialized values
    """
    snapshot = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in AUDIT_EXCLUDED_FIELD_NAMES:
            continue
        snapshot[field.name] = _serialize_field_value(instance, field)
    return snapshot


def build_create_changed_fields(after_snapshot):
    """Build change rows for a creation event from the post-save snapshot.
    Input: after_snapshot - dict of field name to serialized value after save
    Output: list of dicts with 'campo' and 'valor_nuevo' keys for non-empty fields
    """
    return [
        {
            "campo": get_field_label(field_name),
            "valor_nuevo": value,
        }
        for field_name, value in after_snapshot.items()
        if value not in (None, "", [], {})
    ]


def build_update_changed_fields(before_snapshot, after_snapshot):
    """Build change rows for fields whose value changed between two snapshots.
    Input: before_snapshot - dict before save; after_snapshot - dict after save
    Output: list of dicts with 'campo', 'valor_anterior', 'valor_nuevo' for changed fields
    """
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
    """Build change rows for a delete event from the last known snapshot.
    Input: before_snapshot - dict of field name to value before deletion
    Output: list with a single name change row if name exists, else empty list
    """
    if before_snapshot.get("name"):
        return [
            {
                "campo": get_field_label("name"),
                "valor_anterior": before_snapshot.get("name"),
            }
        ]
    return []


def build_m2m_changed_fields(*, field_name, before_values, after_values):
    """Build change rows for a many-to-many update event.
    Input: field_name - M2M field name; before_values - sorted list before change;
           after_values - sorted list after change
    Output: list with a single change row containing campo, valor_anterior, valor_nuevo
    """
    return [
        {
            "campo": get_field_label(field_name),
            "valor_anterior": before_values,
            "valor_nuevo": after_values,
        }
    ]


def _format_list_value(value):
    """Format a list audit value by recursively formatting each element.
    Input: value - a list of raw audit values
    Output: str comma-joined formatted elements, or '-' if result is empty
    """
    return ", ".join(format_display_value(item) for item in value) or "-"


def _format_dict_value(value):
    """Format a dict audit value as preference lines or generic key-value text.
    Input: value - a dict of raw audit values
    Output: str preference lines joined by ' | ', or semicolon-joined key: value pairs, or '-'
    """
    preference_lines = _build_preference_display_lines(value)
    if preference_lines is not None:
        return " | ".join(preference_lines) or "-"
    return (
        "; ".join(f"{key}: {format_display_value(item)}" for key, item in value.items())
        or "-"
    )


def format_display_value(value):
    """Format a raw audit value into human-readable text for exports.
    Input: value - a raw audit field value (list, dict, None, str, or scalar)
    Output: str human-readable representation, or '-' for empty or None values
    """
    if isinstance(value, list):
        return _format_list_value(value)
    if isinstance(value, dict):
        return _format_dict_value(value)
    if value in (None, ""):
        return "-"
    return DISPLAY_VALUE_TRANSLATIONS.get(str(value), str(value))


def _group_preferences_by_state(value):
    """Group time-preference slot entries by their state code.
    Input: value - dict mapping 'DAY_HH:MM' slot keys to state code strings
    Output: dict mapping state code to sorted list of 'Day a las HH:MM' strings
    """
    grouped = {code: [] for code, _ in PREFERENCE_GROUPS}
    for slot_key, state in sorted(value.items(), key=lambda item: item[0]):
        if state not in grouped:
            continue
        day_code, hour = slot_key.split("_", 1)
        grouped[state].append(
            f"{PREFERENCE_DAY_NAMES.get(day_code, day_code)} a las {hour}"
        )
    return grouped


def _format_preference_group(state_code, label, grouped):
    """Format one preference state group into a display line, or return None if empty.
    Input: state_code - preference state key (e.g. 'PREFER_YES');
           label - Spanish group label; grouped - dict from _group_preferences_by_state
    Output: str formatted line (e.g. 'Preferidas: Lunes a las 09:30.'), or None if empty
    """
    entries = grouped.get(state_code, [])
    if not entries:
        return None
    return f"{label}: {', '.join(entries)}."


def _build_preference_display_lines(value):
    """Return formatted display lines for serialized time-preference payloads, or None.
    Input: value - dict that may represent a time_preferences field payload
    Output: list of str display lines grouped by state, or None if not a preference dict
    """
    if not isinstance(value, dict) or not value:
        return None
    if not all(
        isinstance(key, str) and "_" in key and len(key.split("_", 1)[0]) == 3
        for key in value
    ):
        return None

    grouped = _group_preferences_by_state(value)
    return [
        line
        for state_code, label in PREFERENCE_GROUPS
        for line in [_format_preference_group(state_code, label, grouped)]
        if line is not None
    ]


def _get_preference_sections(change):
    """Return preference sections for export when the change targets time preferences.
    Input: change - a changed_fields entry dict with 'campo' and optional value keys
    Output: list of str preference display lines, or None if not a preference field
    """
    if change.get("campo") != "Preferencias horarias":
        return None

    raw_value = (
        change.get("valor_nuevo")
        if "valor_nuevo" in change
        else change.get("valor_anterior")
    )
    return _build_preference_display_lines(raw_value)


def _build_change_export_line(change):
    """Return one export line for a single changed field entry.
    Input: change - a changed_fields entry dict with 'campo' and optional value keys
    Output: str formatted export line, or None if the entry should be skipped
    """
    field_name = change.get("campo", "")
    old_value = format_display_value(change.get("valor_anterior"))
    new_value = format_display_value(change.get("valor_nuevo"))

    if field_name == "Franja horaria preferida" and new_value == "-":
        return None
    if "valor_anterior" in change and "valor_nuevo" in change:
        return f"{field_name}: cambió de {old_value} a {new_value}."
    if "valor_nuevo" in change:
        return f"{field_name}: {new_value}."
    return f"{field_name}: {old_value}."


def format_changed_fields_for_export(changed_fields):
    """Render audit changed_fields payloads as export-friendly text blocks.
    Input: changed_fields - list of change dicts, or None
    Output: str newline-joined export lines for all changed fields
    """
    lines = []
    for change in changed_fields or []:
        preference_sections = _get_preference_sections(change)
        if preference_sections:
            lines.extend(chain([f"{change.get('campo', '')}:"], preference_sections))
            continue

        export_line = _build_change_export_line(change)
        if export_line is not None:
            lines.append(export_line)
    return "\n".join(lines)


def get_current_actor():
    """Return the authenticated actor currently stored in the audit context.
    Input: None
    Output: User instance or None from the current ContextVar
    """
    actor = _AUDIT_ACTOR.get()
    return actor.get("user")


def is_audit_suppressed(*, model, action_type):
    """Return whether audit creation is temporarily disabled for a model/action.
    Input: model - a Django model class; action_type - an AuditActionType value
    Output: bool True if this (entity_type, action_type) pair is suppressed
    """
    return (get_entity_type(model), action_type) in _AUDIT_SUPPRESSION.get()


@contextmanager
def audit_actor_context(*, user=None):
    """Temporarily bind the current authenticated user to audit writes.
    Input: user - authenticated User instance or None
    Output: context manager; sets audit actor for duration of the with-block
    """
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
    """Temporarily suppress audit writes for specific (entity_type, action_type) rules.
    Input: rules - one or more (entity_type_str, action_type_str) tuples to suppress
    Output: context manager; suppresses matching audit events for duration of the with-block
    """
    token = _AUDIT_SUPPRESSION.set(_AUDIT_SUPPRESSION.get().union(rules))
    try:
        yield
    finally:
        _AUDIT_SUPPRESSION.reset(token)


def build_action_detail(*, action_type, model, entity_name, changed_fields=None):
    """Build the Spanish summary sentence stored in the audit detail field.
    Input: action_type - AuditActionType value; model - model class;
           entity_name - str name of the instance; changed_fields - list of change dicts
    Output: str Spanish sentence summarizing the action
    """
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
    """Build the Spanish summary sentence for many-to-many updates.
    Input: model - model class; entity_name - str name of the instance;
           field_name - the M2M field name
    Output: str Spanish sentence describing the M2M update
    """
    entity_phrase = get_entity_phrase(model)
    safe_name = entity_name or "sin nombre"
    return (
        f'Se modificó {entity_phrase} "{safe_name}". '
        f"Se actualizó el campo {get_field_label(field_name)}."
    )


def _resolve_team(team, actor):
    """Return the team to associate with an audit row.
    Input: team - explicit team or None; actor - current User or None
    Output: CollaborationTeam instance, or None if neither team nor actor has one
    """
    if team is not None:
        return team
    if actor is None:
        return None
    return getattr(actor, "active_team", None)


def create_audit_entry(
    *,
    model,
    entity_id,
    entity_name,
    action_type,
    detail,
    changed_fields=None,
    team=None,
):
    """Persist a new audit row using the current audit actor context when available.
    Input: model - model class; entity_id - pk of the entity; entity_name - str name;
           action_type - AuditActionType value; detail - str summary sentence;
           changed_fields - list of change dicts; team - explicit team override
    Output: AuditEntry instance that was created
    """
    actor = get_current_actor()

    return AuditEntry.objects.create(
        team=_resolve_team(team, actor),
        entity_type=get_entity_type(model),
        entity_id=entity_id,
        entity_name=(entity_name or "")[:255],
        action_type=action_type,
        detail=detail,
        changed_fields=changed_fields or [],
        actor=actor,
        actor_name=get_user_display_name(actor),
    )
