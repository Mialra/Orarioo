from rest_framework import permissions, viewsets

from subject.models import Subject
from subject.serializers import SubjectSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    """CRUD API for subjects."""

    queryset = Subject.objects.all().select_related("teacher", "group")
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(updated_by=actor)
