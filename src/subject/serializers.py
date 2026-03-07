from rest_framework import serializers

from subject.models import Subject


class SubjectSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "weekly_hours",
            "duration",
            "preferred_time_slot",
            "stage",
            "type",
            "teacher",
            "teacher_name",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "teacher_name",
        ]

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than zero.")
        return value

    def validate_weekly_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError("Weekly hours must be greater than zero.")
        return value
