from rest_framework import serializers

from classroom.models import Classroom
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from namedEntity.serializers import NamedEntityNameValidationMixin


class ClassroomSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    enforce_case_insensitive_unique_name = True

    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Classroom
        fields = with_audit_fields("name", "is_shared", "team")
        read_only_fields = AUDIT_READ_ONLY_FIELD_NAMES
