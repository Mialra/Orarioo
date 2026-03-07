from rest_framework import serializers

from schedule.models import Schedule


class ScheduleSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Schedule
        fields = [
            "id",
            "name",
            "start_time",
            "end_time",
            "observations",
            "teacher",
            "teacher_name",
            "classroom",
            "classroom_name",
            "group",
            "group_name",
            "users",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "teacher_name",
            "classroom_name",
            "group_name",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate(self, attrs):
        start_time = attrs.get(
            "start_time",
            self.instance.start_time if self.instance else None,
        )
        end_time = attrs.get(
            "end_time",
            self.instance.end_time if self.instance else None,
        )

        if start_time is not None and end_time is not None and end_time <= start_time:
            raise serializers.ValidationError(
                {"end_time": "end_time must be greater than start_time."}
            )

        if self.instance is None and not attrs.get("users"):
            raise serializers.ValidationError(
                {"users": "At least one user must be assigned."}
            )

        if self.instance is not None and "users" in attrs and not attrs.get("users"):
            raise serializers.ValidationError(
                {"users": "At least one user must be assigned."}
            )

        return attrs
