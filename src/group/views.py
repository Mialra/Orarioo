from rest_framework import permissions, viewsets

from group.models import Group
from group.serializers import GroupSerializer


class GroupViewSet(viewsets.ModelViewSet):
    """CRUD API for groups (courses)."""

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(updated_by=actor)
