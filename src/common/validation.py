from rest_framework import serializers


def normalize_time_preferences(value):
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise serializers.ValidationError("time_preferences must be an object.")
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
