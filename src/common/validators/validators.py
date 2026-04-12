from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email as django_validate_email
from rest_framework import serializers

from app.constants import MAX_LENGTH_EXTENDED
from common.errors.exceptions import NON_FIELD_ERRORS_KEY, build_error_entry


def raise_validation_error(field_name, code, message, *, context=None):
    raise serializers.ValidationError(
        {field_name: [build_error_entry(code, message, context=context)]}
    )


def raise_non_field_error(code, message, *, context=None):
    raise serializers.ValidationError(
        {
            NON_FIELD_ERRORS_KEY: [
                build_error_entry(code, message, context=context),
            ]
        }
    )


def validate_and_normalize_required_text(
    value,
    *,
    field_name,
    max_length=None,
    label=None,
    lowercase=False,
):
    label = label or field_name

    if value is None:
        raise_validation_error(
            field_name,
            "REQUIRED_FIELD",
            f"{label} is required.",
            context={"field": field_name},
        )
    if not isinstance(value, str):
        raise_validation_error(
            field_name,
            "INVALID_TYPE",
            f"{label} must be a string.",
            context={"field": field_name, "expected_type": "string"},
        )

    normalized = value.strip()
    if not normalized:
        raise_validation_error(
            field_name,
            "BLANK_FIELD",
            f"{label} cannot be empty or whitespace only.",
            context={"field": field_name},
        )

    if max_length is not None and len(normalized) > max_length:
        raise_validation_error(
            field_name,
            "MAX_LENGTH_EXCEEDED",
            f"{label} cannot be longer than {max_length} characters.",
            context={
                "field": field_name,
                "max_length": max_length,
                "actual_length": len(normalized),
            },
        )

    return normalized.lower() if lowercase else normalized


def normalize_optional_text(
    value,
    *,
    field_name,
    max_length=None,
    label=None,
    lowercase=False,
):
    label = label or field_name

    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise_validation_error(
            field_name,
            "INVALID_TYPE",
            f"{label} must be a string.",
            context={"field": field_name, "expected_type": "string"},
        )

    normalized = value.strip()
    if not normalized:
        return ""

    if max_length is not None and len(normalized) > max_length:
        raise_validation_error(
            field_name,
            "MAX_LENGTH_EXCEEDED",
            f"{label} cannot be longer than {max_length} characters.",
            context={
                "field": field_name,
                "max_length": max_length,
                "actual_length": len(normalized),
            },
        )

    return normalized.lower() if lowercase else normalized


def validate_and_normalize_email(value, *, field_name="email", label="email"):
    normalized = validate_and_normalize_required_text(
        value,
        field_name=field_name,
        label=label,
        max_length=MAX_LENGTH_EXTENDED,
        lowercase=True,
    )

    try:
        django_validate_email(normalized)
    except DjangoValidationError:
        raise_validation_error(
            field_name,
            "INVALID_EMAIL",
            f"{label} must be a valid email address.",
            context={"field": field_name, "value": normalized},
        )

    return normalized


def validate_case_insensitive_unique(
    value,
    *,
    field_name,
    queryset,
    instance=None,
    label=None,
):
    label = label or field_name

    conflict_queryset = queryset.filter(**{f"{field_name}__iexact": value})
    if instance is not None and getattr(instance, "pk", None) is not None:
        conflict_queryset = conflict_queryset.exclude(pk=instance.pk)

    if conflict_queryset.exists():
        raise_validation_error(
            field_name,
            "DUPLICATE_VALUE",
            f"{label} already exists.",
            context={"field": field_name, "value": value},
        )

    return value


def normalize_time_preferences(value):
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise_validation_error(
            "time_preferences",
            "INVALID_TYPE",
            "time_preferences must be an object.",
            context={"field": "time_preferences", "expected_type": "object"},
        )
    return value


def collect_invalid_time_preference_entries(preferences, valid_states):
    invalid_keys = []
    invalid_states_entries = []

    for key, state in preferences.items():
        if not isinstance(key, str):
            invalid_keys.append(key)
            continue
        if state not in valid_states:
            invalid_states_entries.append({"slot": key, "state": state})

    return invalid_keys, invalid_states_entries
