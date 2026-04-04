from rest_framework.pagination import PageNumberPagination

from common.drf import AuditableModelViewSet
from group.models import Group
from group.serializers import GroupSerializer
from main.views import render_admin_dashboard


def admin_groups(request):
    return render_admin_dashboard(request, "groups")


class GroupViewSet(AuditableModelViewSet):
    """CRUD API for groups (courses)."""

    class GroupPagination(PageNumberPagination):
        page_size = 9
        page_size_query_param = "page_size"
        max_page_size = 100

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    pagination_class = GroupPagination
