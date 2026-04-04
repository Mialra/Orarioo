from rest_framework import serializers

from common.serializer_utils import AUDIT_FIELD_NAMES
from group.models import Group
from namedEntity.serializers import NamedEntityNameValidationMixin


class GroupSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    enforce_case_insensitive_unique_name = True

    stage_display = serializers.SerializerMethodField()
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "team",
            "stage",
            "stage_display",
            *AUDIT_FIELD_NAMES,
        ]
        read_only_fields = [
            "id",
            "stage_display",
            *AUDIT_FIELD_NAMES,
        ]

    def get_stage_display(self, obj):
        return obj.get_stage_display()
