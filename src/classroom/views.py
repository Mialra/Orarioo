"""
Admin page entrypoint and API viewset for classrooms.
"""

from classroom.models import Classroom
from classroom.serializers import ClassroomSerializer
from common.admin import StandardTeamScopedCrudViewSet, build_admin_tab_view

admin_classrooms = build_admin_tab_view("classrooms")


class ClassroomViewSet(StandardTeamScopedCrudViewSet):
    """CRUD API for classrooms."""

    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
