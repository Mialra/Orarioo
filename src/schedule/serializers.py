from rest_framework import serializers

from classroom.models import Classroom
from common.serializer_utils import AUDIT_FIELD_NAMES
from common.tenancy import get_active_team
from common.validators.validators import normalize_optional_text, raise_validation_error
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
    subject_type = serializers.CharField(source="subject.type", read_only=True)

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
            "subject_type",
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
            "subject_type",
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
            raise_validation_error(
                "end_time",
                "INVALID_TIME_RANGE",
                "end_time must be greater than start_time.",
                context={"field": "end_time"},
            )

        if self.instance is None and not attrs.get("users"):
            raise_validation_error(
                "users",
                "REQUIRED_COLLECTION",
                "At least one user must be assigned.",
                context={"field": "users"},
            )

        if self.instance is None and not attrs.get("subject"):
            raise_validation_error(
                "subject",
                "REQUIRED_FIELD",
                "This field is required.",
                context={"field": "subject"},
            )

        if (
            self.instance is not None
            and "subject" in attrs
            and attrs.get("subject") is None
        ):
            raise_validation_error(
                "subject",
                "NULL_NOT_ALLOWED",
                "This field may not be null.",
                context={"field": "subject"},
            )

        if self.instance is not None and "users" in attrs and not attrs.get("users"):
            raise_validation_error(
                "users",
                "REQUIRED_COLLECTION",
                "At least one user must be assigned.",
                context={"field": "users"},
            )

        attrs["observations"] = normalize_optional_text(
            attrs.get(
                "observations", self.instance.observations if self.instance else ""
            ),
            field_name="observations",
            label="observations",
        )

        return attrs
