from rest_framework import permissions, viewsets

from classroom.models import Classroom
from classroom.serializers import ClassroomSerializer


class ClassroomViewSet(viewsets.ModelViewSet):
    """CRUD API for classrooms."""

    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(updated_by=actor)
