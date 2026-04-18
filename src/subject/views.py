"""
Admin page entrypoint and API viewset for subjects.
"""

from common.drf import StandardPagination, TeamScopedAuditableModelViewSet
from main.views import render_admin_dashboard
from subject.models import Subject
from subject.serializers import SubjectSerializer


def admin_subjects(request):
    """Render the administration dashboard with the subjects tab selected.
    Input: request - HttpRequest
    Output: HttpResponse with the admin dashboard template
    """
    return render_admin_dashboard(request, "subjects")


class SubjectViewSet(TeamScopedAuditableModelViewSet):
    """CRUD API for subjects."""

    queryset = Subject.objects.all().select_related("teacher", "group")
    serializer_class = SubjectSerializer
    pagination_class = StandardPagination
