"""
Signal handlers that persist audit entries for auditable models and M2M changes.
"""

from django.apps import apps
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)

from auditableEntity.audit import (
    AUDITABLE_MODEL_LABELS,
    build_action_detail,
    build_create_changed_fields,
    build_delete_changed_fields,
    build_m2m_changed_fields,
    build_m2m_detail,
    build_update_changed_fields,
    create_audit_entry,
    get_instance_name,
    is_audit_suppressed,
    snapshot_instance,
)
from auditableEntity.models import AuditActionType

SIGNALS_REGISTERED = False

M2M_AUDITED_FIELDS = (
    ("schedule", "Schedule", "users", "audit_schedule_users_m2m"),
    (
        "subject",
        "Subject",
        "allowed_classrooms",
        "audit_subject_allowed_classrooms_m2m",
    ),
)


def _handle_pre_save(sender, instance, **kwargs):
    """Capture the previous snapshot before an audited update is saved.
    Input: sender - the model class; instance - the instance being saved
    Output: None; sets instance._audit_before_snapshot as a side effect
    """
    if is_audit_suppressed(model=sender, action_type=AuditActionType.UPDATE):
        return

    if not instance.pk:
        return

    previous = sender.objects.filter(pk=instance.pk).first()
    if previous is None:
        return

    instance._audit_before_snapshot = snapshot_instance(previous)


def _create_create_audit_entry(sender, instance, after_snapshot):
    """Persist the audit row for a created instance.
    Input: sender - the model class; instance - the saved instance;
           after_snapshot - dict of field values after save
    Output: None; writes an AuditEntry row as a side effect
    """
    changed_fields = build_create_changed_fields(after_snapshot)
    entity_name = get_instance_name(instance)
    create_audit_entry(
        model=sender,
        entity_id=instance.pk,
        entity_name=entity_name,
        action_type=AuditActionType.CREATE,
        detail=build_action_detail(
            action_type=AuditActionType.CREATE,
            model=sender,
            entity_name=entity_name,
            changed_fields=changed_fields,
        ),
        changed_fields=changed_fields,
        team=getattr(instance, "team", None),
    )


def _create_update_audit_entry(sender, instance, before_snapshot, after_snapshot):
    """Persist the audit row for an updated instance when fields changed.
    Input: sender - the model class; instance - the updated instance;
           before_snapshot - dict before save; after_snapshot - dict after save
    Output: None; writes an AuditEntry row when changed fields exist, else no-op
    """
    changed_fields = build_update_changed_fields(before_snapshot or {}, after_snapshot)
    if not changed_fields:
        return
    if is_audit_suppressed(model=sender, action_type=AuditActionType.UPDATE):
        return

    entity_name = get_instance_name(instance)
    create_audit_entry(
        model=sender,
        entity_id=instance.pk,
        entity_name=entity_name,
        action_type=AuditActionType.UPDATE,
        detail=build_action_detail(
            action_type=AuditActionType.UPDATE,
            model=sender,
            entity_name=entity_name,
            changed_fields=changed_fields,
        ),
        changed_fields=changed_fields,
        team=getattr(instance, "team", None),
    )


def _handle_post_save(sender, instance, created, **kwargs):
    """Create the matching audit entry after an audited save operation.
    Input: sender - the model class; instance - the saved instance;
           created - True if this was a creation, False for updates
    Output: None; delegates to create or update audit entry helpers as a side effect
    """
    after_snapshot = snapshot_instance(instance)

    if created:
        if is_audit_suppressed(model=sender, action_type=AuditActionType.CREATE):
            return
        _create_create_audit_entry(sender, instance, after_snapshot)
        return

    before_snapshot = getattr(instance, "_audit_before_snapshot", None)
    _create_update_audit_entry(sender, instance, before_snapshot, after_snapshot)


def _handle_pre_delete(sender, instance, **kwargs):
    """Capture the last known snapshot before an audited delete.
    Input: sender - the model class; instance - the instance about to be deleted
    Output: None; sets _audit_before_delete_snapshot and _audit_before_delete_name as side effects
    """
    if is_audit_suppressed(model=sender, action_type=AuditActionType.DELETE):
        return

    instance._audit_before_delete_snapshot = snapshot_instance(instance)
    instance._audit_before_delete_name = get_instance_name(instance)


def _handle_post_delete(sender, instance, **kwargs):
    """Create the matching audit entry after an audited delete.
    Input: sender - the model class; instance - the deleted instance
    Output: None; writes a DELETE AuditEntry row as a side effect
    """
    before_snapshot = getattr(instance, "_audit_before_delete_snapshot", {})
    entity_name = getattr(instance, "_audit_before_delete_name", "")
    changed_fields = build_delete_changed_fields(before_snapshot)
    if is_audit_suppressed(model=sender, action_type=AuditActionType.DELETE):
        return

    create_audit_entry(
        model=sender,
        entity_id=instance.pk,
        entity_name=entity_name,
        action_type=AuditActionType.DELETE,
        detail=build_action_detail(
            action_type=AuditActionType.DELETE,
            model=sender,
            entity_name=entity_name,
            changed_fields=changed_fields,
        ),
        changed_fields=changed_fields,
        team=getattr(instance, "team", None),
    )


def _get_m2m_cache_name(field_name):
    """Return the temporary instance attribute used to cache M2M values.
    Input: field_name - the M2M field name being audited
    Output: str attribute name to use on the instance for caching
    """
    return f"_audit_m2m_before_{field_name}"


def _get_sorted_relation_names(instance, field_name):
    """Return the current related item names for an audited M2M field.
    Input: instance - the parent model instance; field_name - the M2M field name
    Output: sorted list of str names for all current related items
    """
    relation_manager = getattr(instance, field_name)
    return sorted(get_instance_name(item) for item in relation_manager.all())


def _clear_cached_m2m_values(instance, field_name):
    """Remove cached M2M values from the instance when they are no longer needed.
    Input: instance - the model instance; field_name - the M2M field name
    Output: None; removes the cache attribute from instance as a side effect
    """
    cache_name = _get_m2m_cache_name(field_name)
    if hasattr(instance, cache_name):
        delattr(instance, cache_name)


def _build_m2m_handler(field_name):
    """Build the signal handler used to audit one many-to-many field.
    Input: field_name - the name of the M2M field to audit
    Output: callable signal handler function bound to field_name
    """

    def _handler(sender, instance, action, reverse, pk_set, **kwargs):
        """Audit many-to-many changes once the relation update completes.
        Input: sender - the through model; instance - the parent model instance;
               action - the m2m signal action string; reverse - whether the relation is reversed;
               pk_set - the set of related pks being added or removed
        Output: None; creates an AuditEntry as a side effect when values change
        """
        if reverse:
            return

        if action in {"pre_add", "pre_remove", "pre_clear"}:
            setattr(
                instance,
                _get_m2m_cache_name(field_name),
                _get_sorted_relation_names(instance, field_name),
            )
            return

        if action not in {"post_add", "post_remove", "post_clear"}:
            return

        before_values = getattr(instance, _get_m2m_cache_name(field_name), [])
        after_values = _get_sorted_relation_names(instance, field_name)
        if before_values == after_values:
            _clear_cached_m2m_values(instance, field_name)
            return
        entity_name = get_instance_name(instance)
        changed_fields = build_m2m_changed_fields(
            field_name=field_name,
            before_values=before_values,
            after_values=after_values,
        )
        create_audit_entry(
            model=instance.__class__,
            entity_id=instance.pk,
            entity_name=entity_name,
            action_type=AuditActionType.UPDATE,
            detail=build_m2m_detail(
                model=instance.__class__,
                entity_name=entity_name,
                field_name=field_name,
            ),
            changed_fields=changed_fields,
            team=getattr(instance, "team", None),
        )
        _clear_cached_m2m_values(instance, field_name)

    return _handler


def _connect_model_signals(label):
    """Connect save and delete audit signals for one model label.
    Input: label - app_label.ModelName string (e.g. 'teacher.Teacher')
    Output: None; registers pre_save, post_save, pre_delete, post_delete signals as side effects
    """
    sender = apps.get_model(label)
    pre_save.connect(
        _handle_pre_save,
        sender=sender,
        dispatch_uid=f"audit_pre_save_{label}",
    )
    post_save.connect(
        _handle_post_save,
        sender=sender,
        dispatch_uid=f"audit_post_save_{label}",
    )
    pre_delete.connect(
        _handle_pre_delete,
        sender=sender,
        dispatch_uid=f"audit_pre_delete_{label}",
    )
    post_delete.connect(
        _handle_post_delete,
        sender=sender,
        dispatch_uid=f"audit_post_delete_{label}",
    )


def _connect_m2m_signal(app_label, model_name, field_name, dispatch_uid):
    """Connect the audit signal for one audited many-to-many field.
    Input: app_label - Django app label; model_name - model class name;
           field_name - M2M field name; dispatch_uid - unique signal identifier
    Output: None; registers an m2m_changed signal handler as a side effect
    """
    model = apps.get_model(app_label, model_name)
    through_model = model._meta.get_field(field_name).remote_field.through
    m2m_changed.connect(
        _build_m2m_handler(field_name),
        sender=through_model,
        dispatch_uid=dispatch_uid,
    )


def register_audit_signals():
    """Register all audit-related Django signals exactly once.
    Input: None
    Output: None; connects all model and M2M audit signals as a side effect
    """
    global SIGNALS_REGISTERED

    if SIGNALS_REGISTERED:
        return

    for label in AUDITABLE_MODEL_LABELS:
        _connect_model_signals(label)
    for app_label, model_name, field_name, dispatch_uid in M2M_AUDITED_FIELDS:
        _connect_m2m_signal(app_label, model_name, field_name, dispatch_uid)

    SIGNALS_REGISTERED = True
