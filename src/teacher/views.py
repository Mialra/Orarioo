from common.drf import AuditableModelViewSet
from teacher.models import Teacher
from teacher.serializers import TeacherSerializer


class TeacherViewSet(AuditableModelViewSet):
    """CRUD API for teachers."""

    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
