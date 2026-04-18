"""
Serializer for group CRUD operations with stage display and shared audit fields.
"""

from rest_framework import serializers

from common.serializers import TeamScopedModelSerializerMixin
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from group.models import Group
from namedEntity.serializers import NamedEntityNameValidationMixin

GROUP_SERIALIZER_FIELDS = with_audit_fields("name", "team", "stage", "stage_display")


class GroupSerializer(
    TeamScopedModelSerializerMixin,
    NamedEntityNameValidationMixin,
    serializers.ModelSerializer,
):
    """Validate and serialize groups using the shared NamedEntity rules."""

    enforce_case_insensitive_unique_name = True

    stage_display = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = GROUP_SERIALIZER_FIELDS
        read_only_fields = [*AUDIT_READ_ONLY_FIELD_NAMES, "stage_display"]

    def get_stage_display(self, obj):
        """Return the human-readable label for the group's educational stage.
        Input: obj - Group instance
        Output: str display label for the stage choice
        """
        return obj.get_stage_display()
