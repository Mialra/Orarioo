from rest_framework import serializers

from teacher.models import Teacher


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = [
            "id",
            "name",
            "max_weekly_hours",
            "working_hours",
            "preferences",
            "availability",
            "unavailability",
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
        ]

    def validate(self, attrs):
        max_weekly_hours = attrs.get(
            "max_weekly_hours",
            self.instance.max_weekly_hours if self.instance else None,
        )
        working_hours = attrs.get(
            "working_hours",
            self.instance.working_hours if self.instance else 0,
        )

        if max_weekly_hours is not None and working_hours > max_weekly_hours:
            raise serializers.ValidationError(
                {
                    "working_hours": (
                        "working_hours cannot be greater than max_weekly_hours."
                    )
                }
            )

        return attrs
