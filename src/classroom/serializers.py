"""
Serializer for classroom CRUD operations with shared audit fields.
"""

from rest_framework import serializers

from classroom.models import Classroom
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields
from namedEntity.serializers import NamedEntityNameValidationMixin

CLASSROOM_SERIALIZER_FIELDS = with_audit_fields("name", "is_shared", "team")


class ClassroomSerializer(NamedEntityNameValidationMixin, serializers.ModelSerializer):
    """Validate and serialize classrooms using the shared NamedEntity rules."""

    enforce_case_insensitive_unique_name = True

    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Classroom
        fields = CLASSROOM_SERIALIZER_FIELDS
        read_only_fields = AUDIT_READ_ONLY_FIELD_NAMES
