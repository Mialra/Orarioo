from rest_framework import serializers

from common.serializer_utils import AUDIT_FIELD_NAMES
from common.validation import (
    collect_invalid_time_preference_entries,
    normalize_optional_text,
    normalize_time_preferences,
)
from namedEntity.serializers import NamedEntityNameValidationMixin
from subject.models import Subject, SubjectTimePreferenceState


class SubjectSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    enforce_case_insensitive_unique_name = True

    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "weekly_hours",
            "duration",
            "preferred_time_slot",
            "required_classroom_type",
            "time_preferences",
            "stage",
            "type",
            "teacher",
            "teacher_name",
            "group",
            "group_name",
            *AUDIT_FIELD_NAMES,
        ]
        read_only_fields = [
            "id",
            "duration",
            *AUDIT_FIELD_NAMES,
            "teacher_name",
            "group_name",
        ]

    def validate_weekly_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError("Weekly hours must be greater than zero.")
        return value

    def validate_preferred_time_slot(self, value):
        return normalize_optional_text(
            value,
            field_name="preferred_time_slot",
            max_length=150,
        )

    def validate_required_classroom_type(self, value):
        return normalize_optional_text(
            value,
            field_name="required_classroom_type",
            max_length=150,
        )

    def validate_time_preferences(self, value):
        value = normalize_time_preferences(value)

        valid_states = {state.value for state in SubjectTimePreferenceState}
        invalid_keys, invalid_values = collect_invalid_time_preference_entries(
            value,
            valid_states,
        )

        if invalid_keys:
            raise serializers.ValidationError(
                f"All time preference keys must be strings. Invalid keys: {invalid_keys}"
            )
        if invalid_values:
            raise serializers.ValidationError(
                {
                    "invalid_states": invalid_values,
                    "allowed": sorted(valid_states),
                }
            )

        return value
