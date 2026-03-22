from common.drf import AuditableModelViewSet

from group.models import Group
from group.serializers import GroupSerializer


class GroupViewSet(AuditableModelViewSet):
    """CRUD API for groups (courses)."""

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
