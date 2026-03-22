from rest_framework import serializers

from common.serializer_utils import AUDIT_FIELD_NAMES
from schedule.models import Schedule


class ScheduleSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

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
            "subject",
            "subject_name",
            "users",
            *AUDIT_FIELD_NAMES,
        ]
        read_only_fields = [
            "id",
            "teacher_name",
            "classroom_name",
            "group_name",
            "subject_name",
            *AUDIT_FIELD_NAMES,
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

        if self.instance is None and not attrs.get("subject"):
            raise serializers.ValidationError({"subject": "This field is required."})

        if (
            self.instance is not None
            and "subject" in attrs
            and attrs.get("subject") is None
        ):
            raise serializers.ValidationError(
                {"subject": "This field may not be null."}
            )

        if self.instance is not None and "users" in attrs and not attrs.get("users"):
            raise serializers.ValidationError(
                {"users": "At least one user must be assigned."}
            )

        return attrs
