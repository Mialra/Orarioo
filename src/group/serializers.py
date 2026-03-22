from rest_framework import serializers

from common.serializer_utils import AUDIT_FIELD_NAMES
from group.models import Group


class GroupSerializer(serializers.ModelSerializer):
    stage_display = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
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
