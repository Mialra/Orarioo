from rest_framework import serializers

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
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "stage_display",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def get_stage_display(self, obj):
        return obj.get_stage_display()
