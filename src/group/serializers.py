"""
Serializer for group CRUD operations with stage display and shared audit fields.
"""

from rest_framework import serializers

from common.serializer_utils import (AUDIT_READ_ONLY_FIELD_NAMES,
                                     with_audit_fields)
from common.serializers import TeamScopedModelSerializerMixin
from common.stages import DEFAULT_STAGE_COLORS, canonical_group_stage
from common.tenancy import get_active_team
from group.models import Group
from namedEntity.serializers import NamedEntityNameValidationMixin

GROUP_SERIALIZER_FIELDS = with_audit_fields(
    "name",
    "team",
    "stage",
    "stage_display",
    "stage_color",
)

_STAGE_DISPLAY = {
    "PRESCHOOL": "Infantil",
    "preschool": "Infantil",
    "PRIMARY": "Primaria",
    "primary": "Primaria",
    "SECONDARY": "ESO",
    "secondary": "ESO",
    "ALEVELS": "Bachillerato",
    "alevels": "Bachillerato",
}


class GroupSerializer(
    TeamScopedModelSerializerMixin,
    NamedEntityNameValidationMixin,
    serializers.ModelSerializer,
):
    """Validate and serialize groups using the shared NamedEntity rules."""

    enforce_case_insensitive_unique_name = True

    stage_display = serializers.SerializerMethodField()
    stage_color = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = GROUP_SERIALIZER_FIELDS
        read_only_fields = [
            *AUDIT_READ_ONLY_FIELD_NAMES,
            "stage_display",
            "stage_color",
        ]

    def get_stage_display(self, obj):
        """Return the human-readable label for the group's educational stage.
        Input: obj - Group instance
        Output: str display label for the stage
        """
        return _STAGE_DISPLAY.get(obj.stage, obj.stage)

    def get_stage_color(self, obj):
        """Return the configured color for the group's educational stage."""
        stage_code = canonical_group_stage(obj.stage, default=None) or obj.stage
        config = getattr(getattr(obj, "team", None), "schedule_config", None) or {}
        stage_cfg = config.get(stage_code) or {}
        return stage_cfg.get("color") or DEFAULT_STAGE_COLORS.get(stage_code, "blue")

    def validate_stage(self, value):
        """Allow only stages configured for the active team, keeping legacy lowercase values valid."""
        request = self.context.get("request")
        team = self.instance.team if self.instance else get_active_team(request)
        allowed_stage_codes = set((getattr(team, "schedule_config", None) or {}).keys())
        if not allowed_stage_codes:
            allowed_stage_codes = {str(code) for code in DEFAULT_STAGE_COLORS.keys()}

        canonical_stage = canonical_group_stage(value, default=None)
        if canonical_stage not in allowed_stage_codes:
            raise serializers.ValidationError("Invalid stage.")
        return value
