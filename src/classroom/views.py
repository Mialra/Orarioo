from classroom.models import Classroom
from classroom.serializers import ClassroomSerializer
from common.drf import AuditableModelViewSet


class ClassroomViewSet(AuditableModelViewSet):
    """CRUD API for classrooms."""

    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
