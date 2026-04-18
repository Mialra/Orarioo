"""
Admin page entrypoint and API viewset for groups (courses).
"""

from common.admin import StandardTeamScopedCrudViewSet, build_admin_tab_view
from group.models import Group
from group.serializers import GroupSerializer

admin_groups = build_admin_tab_view("groups")


class GroupViewSet(StandardTeamScopedCrudViewSet):
    """CRUD API for groups (courses)."""

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
