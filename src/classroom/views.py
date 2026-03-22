from common.drf import AuditableModelViewSet

from classroom.models import Classroom
from classroom.serializers import ClassroomSerializer


class ClassroomViewSet(AuditableModelViewSet):
    """CRUD API for classrooms."""

    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
