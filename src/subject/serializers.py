"""
Serializer for subject CRUD operations with team-scoped FK validation and audit fields.
"""

from rest_framework import serializers

from app.constants import MAX_LENGTH_EXTENDED, STRING_MAX_LENGTH
from classroom.models import Classroom
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from common.tenancy import get_active_team
from common.validators import (
    collect_invalid_time_preference_entries,
    normalize_optional_text,
    normalize_time_preferences,
    raise_validation_error,
)
from group.models import Group
from namedEntity.serializers import NamedEntityNameValidationMixin
from subject.models import Subject, SubjectTimePreferenceState
from teacher.models import Teacher

SUBJECT_SERIALIZER_FIELDS = with_audit_fields(
    "name",
    "team",
    "weekly_hours",
    "duration",
    "preferred_time_slot",
    "time_preferences",
    "stage",
    "type",
    "teacher",
    "teacher_name",
    "group",
    "group_name",
    "allowed_classrooms",
    "allowed_classroom_names",
)


class SubjectSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    """Validate and serialize subjects using the shared NamedEntity rules."""

    enforce_case_insensitive_unique_name = True
    name_max_length = MAX_LENGTH_EXTENDED

    team = serializers.PrimaryKeyRelatedField(read_only=True)
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    allowed_classroom_names = serializers.SerializerMethodField(read_only=True)

    def __init__(self, *args, **kwargs):
        """Restrict FK querysets to the active team so only valid related objects are selectable.
        Input: *args, **kwargs - passed through to ModelSerializer
        Output: None; side-effect: filters teacher, group, and allowed_classrooms querysets
        """
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request or not getattr(request, "user", None):
            return

        active_team = get_active_team(request)
        self.fields["teacher"].queryset = Teacher.objects.filter(team=active_team)
        self.fields["group"].queryset = Group.objects.filter(team=active_team)
        self.fields["allowed_classrooms"].queryset = Classroom.objects.filter(
            team=active_team
        )

    class Meta:
        model = Subject
        fields = SUBJECT_SERIALIZER_FIELDS
        read_only_fields = [
            *AUDIT_READ_ONLY_FIELD_NAMES,
            "duration",
            "teacher_name",
            "group_name",
            "allowed_classroom_names",
        ]

    def validate_weekly_hours(self, value):
        """Ensure weekly_hours is a positive integer below the 168-hour weekly limit.
        Input: value - int submitted for weekly_hours
        Output: int validated value; raises ValidationError if out of range
        """
        if value <= 0:
            raise_validation_error(
                "weekly_hours",
                "INVALID_POSITIVE_INTEGER",
                "Weekly hours must be greater than zero.",
                context={"field": "weekly_hours", "value": value},
            )
        if value >= 168:
            raise_validation_error(
                "weekly_hours",
                "WEEKLY_HOURS_EXCEEDS_LIMIT",
                "Weekly hours cannot be 168 or more.",
                context={"field": "weekly_hours", "value": value},
            )
        return value

    def validate_preferred_time_slot(self, value):
        """Normalize the preferred_time_slot text, trimming whitespace and enforcing max length.
        Input: value - str submitted for preferred_time_slot
        Output: str normalized value, or raises ValidationError if too long
        """
        return normalize_optional_text(
            value,
            field_name="preferred_time_slot",
            label="preferred_time_slot",
            max_length=STRING_MAX_LENGTH,
        )

    def validate_time_preferences(self, value):
        """Normalize and validate the time_preferences JSON map against allowed states.
        Input: value - dict mapping slot keys to SubjectTimePreferenceState values
        Output: dict normalized preferences; raises ValidationError on invalid keys or states
        """
        value = normalize_time_preferences(value)

        valid_states = {state.value for state in SubjectTimePreferenceState}
        invalid_keys, invalid_values = collect_invalid_time_preference_entries(
            value,
            valid_states,
        )

        if invalid_keys:
            raise_validation_error(
                "time_preferences",
                "INVALID_TIME_PREFERENCE_KEY",
                "All time preference keys must be strings.",
                context={
                    "field": "time_preferences",
                    "invalid_keys": invalid_keys,
                },
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

        return value

    def get_allowed_classroom_names(self, obj):
        """Return the list of names of classrooms allowed for this subject.
        Input: obj - Subject instance
        Output: list of str classroom names
        """
        return list(obj.allowed_classrooms.values_list("name", flat=True))
