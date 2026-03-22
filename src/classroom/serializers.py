from rest_framework import serializers

from classroom.models import Classroom
from common.serializer_utils import AUDIT_READ_ONLY_FIELD_NAMES, with_audit_fields


class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = with_audit_fields("name", "classroom_type")
        read_only_fields = AUDIT_READ_ONLY_FIELD_NAMES
