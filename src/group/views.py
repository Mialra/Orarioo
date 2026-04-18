"""
Admin page entrypoint and API viewset for groups (courses).
"""

from common.drf import StandardPagination, TeamScopedAuditableModelViewSet
from group.models import Group
from group.serializers import GroupSerializer
from main.views import render_admin_dashboard


def admin_groups(request):
    """Render the administration dashboard with the groups tab selected."""
    return render_admin_dashboard(request, "groups")


class GroupViewSet(TeamScopedAuditableModelViewSet):
    """CRUD API for groups (courses)."""

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    pagination_class = StandardPagination
