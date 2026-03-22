from rest_framework import serializers

from classroom.models import Classroom
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from common.validation import normalize_optional_text
from namedEntity.serializers import NamedEntityNameValidationMixin


class ClassroomSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    enforce_case_insensitive_unique_name = True

    class Meta:
        model = Classroom
        fields = with_audit_fields("name", "classroom_type")
        read_only_fields = AUDIT_READ_ONLY_FIELD_NAMES

    def validate_classroom_type(self, value):
        return normalize_optional_text(
            value,
            field_name="classroom_type",
            max_length=150,
        )
