from rest_framework import serializers

from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from common.validation import (
    collect_invalid_time_preference_entries,
    normalize_time_preferences,
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
            raise serializers.ValidationError(
                {
                    "working_hours": (
                        "working_hours cannot be greater than max_weekly_hours."
                    )
                }
            )

        time_preferences = attrs.get(
            "time_preferences",
            self.instance.time_preferences if self.instance else {},
        )
        try:
            normalized_time_preferences = normalize_time_preferences(time_preferences)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError(
                {"time_preferences": str(exc.detail[0])}
            ) from exc

        valid_states = {state.value for state in TeacherTimePreferenceState}
        _, invalid_values = collect_invalid_time_preference_entries(
            normalized_time_preferences,
            valid_states,
        )

        if invalid_values:
            raise serializers.ValidationError(
                {
                    "time_preferences": {
                        "invalid_states": invalid_values,
                        "allowed": sorted(valid_states),
                    }
                }
            )

        attrs["time_preferences"] = normalized_time_preferences
        return attrs
