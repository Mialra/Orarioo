"""
Serializer for subject CRUD operations with team-scoped FK validation and audit fields.
"""

from rest_framework import serializers

from app.constants import MAX_LENGTH_EXTENDED, STRING_MAX_LENGTH
from classroom.models import Classroom
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from common.serializers import TeamScopedModelSerializerMixin
from common.stages import DEFAULT_STAGE_COLORS, canonical_group_stage
from common.validators import (
    normalize_optional_text,
    raise_validation_error,
    validate_time_preferences,
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
    "stage_color",
    "type",
    "teacher",
    "teacher_name",
    "group",
    "group_name",
    "mandatory_classroom",
    "mandatory_classroom_name",
)
# NOTE: `stage` and `stage_color` are read-only derived fields (from group.stage); not DB columns.


class SubjectSerializer(
    TeamScopedModelSerializerMixin,
    NamedEntityNameValidationMixin,
    serializers.ModelSerializer,
):
    """Validate and serialize subjects using the shared NamedEntity rules."""

    enforce_case_insensitive_unique_name = True
    name_max_length = MAX_LENGTH_EXTENDED
    team_scoped_field_models = {
        "teacher": Teacher,
        "group": Group,
        "mandatory_classroom": Classroom,
    }
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    mandatory_classroom_name = serializers.CharField(
        source="mandatory_classroom.name", read_only=True, default=None
    )
    stage = serializers.SerializerMethodField(read_only=True)
    stage_color = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Subject
        fields = SUBJECT_SERIALIZER_FIELDS
        read_only_fields = [
            *AUDIT_READ_ONLY_FIELD_NAMES,
            "duration",
            "teacher_name",
            "group_name",
            "mandatory_classroom_name",
            "stage",
            "stage_color",
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
        return validate_time_preferences(
            value,
            valid_states={state.value for state in SubjectTimePreferenceState},
        )

    def get_stage(self, obj):
        """Return the canonical stage code derived from the subject's group."""
        return canonical_group_stage(getattr(obj.group, "stage", None), default=None)

    def get_stage_color(self, obj):
        """Return the configured color for the subject's educational stage (derived from group)."""
        stage_code = canonical_group_stage(
            getattr(obj.group, "stage", None), default=None
        )
        config = getattr(getattr(obj, "team", None), "schedule_config", None) or {}
        stage_cfg = config.get(stage_code) or {}
        return stage_cfg.get("color") or DEFAULT_STAGE_COLORS.get(stage_code, "blue")
