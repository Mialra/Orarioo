"""
Admin page entrypoint and API viewset for classrooms.
"""

from classroom.models import Classroom
from classroom.serializers import ClassroomSerializer
from common.drf import StandardPagination, TeamScopedAuditableModelViewSet
from main.views import render_admin_dashboard


def admin_classrooms(request):
    """Render the administration dashboard with the classroom tab selected."""
    return render_admin_dashboard(request, "classrooms")


class ClassroomViewSet(TeamScopedAuditableModelViewSet):
    """CRUD API for classrooms."""

    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    pagination_class = StandardPagination
