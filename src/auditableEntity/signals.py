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

_unused_SIGNALS_REGISTERED = False


def _handle_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        return

    previous = sender.objects.filter(pk=instance.pk).first()
    if previous is None:
        return

    instance._audit_before_snapshot = snapshot_instance(previous)
    instance._audit_before_name = get_instance_name(previous)


def _handle_post_save(sender, instance, created, **kwargs):
    after_snapshot = snapshot_instance(instance)
    entity_name = get_instance_name(instance)

    if created:
        if is_audit_suppressed(model=sender, action_type=AuditActionType.CREATE):
            return
        changed_fields = build_create_changed_fields(after_snapshot)
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
        return

    before_snapshot = getattr(instance, "_audit_before_snapshot", None)
    changed_fields = build_update_changed_fields(before_snapshot or {}, after_snapshot)
    if not changed_fields:
        return
    if is_audit_suppressed(model=sender, action_type=AuditActionType.UPDATE):
        return

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


def _handle_pre_delete(sender, instance, **kwargs):
    instance._audit_before_delete_snapshot = snapshot_instance(instance)
    instance._audit_before_delete_name = get_instance_name(instance)


def _handle_post_delete(sender, instance, **kwargs):
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


def _build_m2m_handler(field_name):
    def _handler(sender, instance, action, reverse, pk_set, **kwargs):
        if reverse:
            return

        cache_name = f"_audit_m2m_before_{field_name}"
        relation_manager = getattr(instance, field_name)

        if action in {"pre_add", "pre_remove", "pre_clear"}:
            setattr(
                instance,
                cache_name,
                sorted(get_instance_name(item) for item in relation_manager.all()),
            )
            return

        if action not in {"post_add", "post_remove", "post_clear"}:
            return

        before_values = getattr(instance, cache_name, [])
        after_values = sorted(
            get_instance_name(item) for item in relation_manager.all()
        )
        if before_values == after_values:
            if hasattr(instance, cache_name):
                delattr(instance, cache_name)
            return
        changed_fields = build_m2m_changed_fields(
            field_name=field_name,
            before_values=before_values,
            after_values=after_values,
        )
        create_audit_entry(
            model=instance.__class__,
            entity_id=instance.pk,
            entity_name=get_instance_name(instance),
            action_type=AuditActionType.UPDATE,
            detail=build_m2m_detail(
                model=instance.__class__,
                entity_name=get_instance_name(instance),
                field_name=field_name,
            ),
            changed_fields=changed_fields,
            team=getattr(instance, "team", None),
        )
        if hasattr(instance, cache_name):
            delattr(instance, cache_name)

    return _handler


def register_audit_signals():
    global _unused_SIGNALS_REGISTERED

    if _unused_SIGNALS_REGISTERED:
        return

    for label in AUDITABLE_MODEL_LABELS:
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

    schedule_model = apps.get_model("schedule", "Schedule")
    subject_model = apps.get_model("subject", "Subject")

    m2m_changed.connect(
        _build_m2m_handler("users"),
        sender=schedule_model._meta.get_field("users").remote_field.through,
        dispatch_uid="audit_schedule_users_m2m",
    )
    m2m_changed.connect(
        _build_m2m_handler("allowed_classrooms"),
        sender=subject_model._meta.get_field("allowed_classrooms").remote_field.through,
        dispatch_uid="audit_subject_allowed_classrooms_m2m",
    )

    _unused_SIGNALS_REGISTERED = True
