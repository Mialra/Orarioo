from rest_framework import serializers

from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from common.validators import (
    collect_invalid_time_preference_entries,
    normalize_time_preferences,
    raise_validation_error,
)
from namedEntity.serializers import NamedEntityNameValidationMixin
from teacher.models import Teacher, TeacherTimePreferenceState


class TeacherSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    enforce_case_insensitive_unique_name = True

    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Teacher
        fields = with_audit_fields(
            "name",
            "max_weekly_hours",
            "working_hours",
            "time_preferences",
            "team",
        )
        read_only_fields = AUDIT_READ_ONLY_FIELD_NAMES

    def validate(self, attrs):
        max_weekly_hours = attrs.get(
            "max_weekly_hours",
            self.instance.max_weekly_hours if self.instance else None,
        )
        working_hours = attrs.get(
            "working_hours",
            self.instance.working_hours if self.instance else 0,
        )

        if max_weekly_hours is not None and working_hours > max_weekly_hours:
            raise_validation_error(
                "working_hours",
                "INVALID_HOUR_RANGE",
                "working_hours cannot be greater than max_weekly_hours.",
                context={
                    "field": "working_hours",
                    "max_weekly_hours": max_weekly_hours,
                    "working_hours": working_hours,
                },
            )

        time_preferences = attrs.get(
            "time_preferences",
            self.instance.time_preferences if self.instance else {},
        )
        normalized_time_preferences = normalize_time_preferences(time_preferences)

        valid_states = {state.value for state in TeacherTimePreferenceState}
        _, invalid_values = collect_invalid_time_preference_entries(
            normalized_time_preferences,
            valid_states,
        )

        if invalid_values:
            raise_validation_error(
                "time_preferences",
                "INVALID_TIME_PREFERENCE_STATE",
                "One or more time preference states are invalid.",
                context={
                    "field": "time_preferences",
                    "invalid_states": invalid_values,
                    "allowed": sorted(valid_states),
                },
            )

        attrs["time_preferences"] = normalized_time_preferences
        return attrs

    def validate_max_weekly_hours(self, value):
        if value >= 168:
            raise_validation_error(
                "max_weekly_hours",
                "WEEKLY_HOURS_EXCEEDS_LIMIT",
                "Maximum weekly hours cannot be 168 or more.",
                context={"field": "max_weekly_hours", "value": value},
            )
        return value
