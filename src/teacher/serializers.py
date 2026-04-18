"""
Serializer for teacher CRUD operations with hour-range validation and audit fields.
"""

from rest_framework import serializers

from common.serializers import TeamScopedModelSerializerMixin
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from common.validators import (
    raise_validation_error,
    validate_time_preferences,
)
from namedEntity.serializers import NamedEntityNameValidationMixin
from teacher.models import Teacher, TeacherTimePreferenceState


class TeacherSerializer(
    TeamScopedModelSerializerMixin,
    NamedEntityNameValidationMixin,
    serializers.ModelSerializer,
):
    """Validate and serialize teachers using the shared NamedEntity rules."""

    enforce_case_insensitive_unique_name = True

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
        """Cross-validate working_hours against max_weekly_hours and normalize time_preferences.
        Input: attrs - dict of deserialized field values
        Output: dict validated attrs with normalized time_preferences; raises ValidationError on constraint violations
        """
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
        attrs["time_preferences"] = validate_time_preferences(
            time_preferences,
            valid_states={state.value for state in TeacherTimePreferenceState},
            require_string_keys=False,
        )
        return attrs

    def validate_max_weekly_hours(self, value):
        """Ensure max_weekly_hours is below the 168-hour weekly limit.
        Input: value - int submitted for max_weekly_hours
        Output: int validated value; raises ValidationError if >= 168
        """
        if value >= 168:
            raise_validation_error(
                "max_weekly_hours",
                "WEEKLY_HOURS_EXCEEDS_LIMIT",
                "Maximum weekly hours cannot be 168 or more.",
                context={"field": "max_weekly_hours", "value": value},
            )
        return value
