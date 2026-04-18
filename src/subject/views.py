"""
Admin page entrypoint and API viewset for subjects.
"""

from common.admin import StandardTeamScopedCrudViewSet, build_admin_tab_view
from subject.models import Subject
from subject.serializers import SubjectSerializer

admin_subjects = build_admin_tab_view("subjects")


class SubjectViewSet(StandardTeamScopedCrudViewSet):
    """CRUD API for subjects."""

    queryset = Subject.objects.all().select_related("teacher", "group")
    serializer_class = SubjectSerializer
