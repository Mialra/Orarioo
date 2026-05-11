"""Serializer for the Schedule model with domain-level validations."""

from rest_framework import serializers

from classroom.models import Classroom
from common.serializer_utils import AUDIT_FIELD_NAMES
from common.serializers import TeamScopedModelSerializerMixin
from common.validators import normalize_optional_text, raise_validation_error
from group.models import Group
from namedEntity.serializers import NamedEntityNameValidationMixin
from schedule.models import Schedule
from subject.models import Subject
from teacher.models import Teacher
from user.models import User


class ScheduleSerializer(
    TeamScopedModelSerializerMixin,
    NamedEntityNameValidationMixin,
    serializers.ModelSerializer,
):
    team_scoped_field_models = {
        "teacher": Teacher,
        "classroom": Classroom,
        "group": Group,
        "subject": Subject,
    }
    team_scoped_field_querysets = {
        "users": lambda active_team: User.objects.filter(
            collaboration_teams=active_team,
            is_enabled=True,
        ).distinct()
    }
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    group_stage = serializers.CharField(source="group.stage", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_type = serializers.CharField(source="subject.type", read_only=True)

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
        """Validate Schedule business rules at the object level.
        Input: attrs - dict of individually validated fields
        Output: attrs with normalised observations; raises ValidationError if:
                end_time <= start_time, users empty on create, subject null on create,
                or subject explicitly set to null on update
        """
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

        classroom = attrs.get(
            "classroom", self.instance.classroom if self.instance else None
        )
        group = attrs.get("group", self.instance.group if self.instance else None)
        if classroom is None:
            raise_validation_error(
                "classroom",
                "REQUIRED_FIELD",
                "This field is required.",
                context={"field": "classroom"},
            )
        if group is None:
            raise_validation_error(
                "group",
                "REQUIRED_FIELD",
                "This field is required.",
                context={"field": "group"},
            )

        attrs["observations"] = normalize_optional_text(
            attrs.get(
                "observations", self.instance.observations if self.instance else ""
            ),
            field_name="observations",
            label="observations",
        )

        return attrs
