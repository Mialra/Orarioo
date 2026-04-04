from rest_framework import serializers

from common.serializer_utils import AUDIT_FIELD_NAMES
from common.tenancy import get_active_team
from common.validation import normalize_optional_text
from classroom.models import Classroom
from group.models import Group
from namedEntity.serializers import NamedEntityNameValidationMixin
from schedule.models import Schedule
from subject.models import Subject
from teacher.models import Teacher
from user.models import User


class ScheduleSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    group_stage = serializers.CharField(source="group.stage", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request or not getattr(request, "user", None):
            return

        active_team = get_active_team(request)
        self.fields["teacher"].queryset = Teacher.objects.filter(team=active_team)
        self.fields["classroom"].queryset = Classroom.objects.filter(team=active_team)
        self.fields["group"].queryset = Group.objects.filter(team=active_team)
        self.fields["subject"].queryset = Subject.objects.filter(team=active_team)
        self.fields["users"].queryset = User.objects.filter(
            collaboration_teams=active_team,
            is_enabled=True,
        ).distinct()

    class Meta:
        model = Schedule
        fields = [
            "id",
            "name",
            "team",
            "start_time",
            "end_time",
            "observations",
            "teacher",
            "teacher_name",
            "classroom",
            "classroom_name",
            "group",
            "group_name",
            "group_stage",
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
            "group_stage",
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

        attrs["observations"] = normalize_optional_text(
            attrs.get(
                "observations", self.instance.observations if self.instance else ""
            ),
            field_name="observations",
        )

        return attrs
