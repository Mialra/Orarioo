from rest_framework import serializers


def normalize_time_preferences(value):
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise serializers.ValidationError("time_preferences must be an object.")
    return value


def validate_and_normalize_required_text(value, *, field_name, max_length=None):
    if value is None:
        raise serializers.ValidationError(f"{field_name} is required.")
    if not isinstance(value, str):
        raise serializers.ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()
    if not normalized:
        raise serializers.ValidationError(
            f"{field_name} cannot be empty or whitespace only."
        )

    if max_length is not None and len(normalized) > max_length:
        raise serializers.ValidationError(
            f"{field_name} cannot be longer than {max_length} characters."
        )

    return normalized


def normalize_optional_text(value, *, field_name, max_length=None):
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise serializers.ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()
    if not normalized:
        return ""

    if max_length is not None and len(normalized) > max_length:
        raise serializers.ValidationError(
            f"{field_name} cannot be longer than {max_length} characters."
        )

    return normalized


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
