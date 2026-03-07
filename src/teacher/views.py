from rest_framework import permissions, viewsets

from teacher.models import Teacher
from teacher.serializers import TeacherSerializer


class TeacherViewSet(viewsets.ModelViewSet):
    """CRUD API for teachers."""

    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(updated_by=actor)
