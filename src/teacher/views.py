"""
Admin page entrypoint and API viewset for teachers.
"""

from django.db.models.functions import Lower

from common.admin import StandardTeamScopedCrudViewSet, build_admin_tab_view
from teacher.models import Teacher
from teacher.serializers import TeacherSerializer

admin_teachers = build_admin_tab_view("teachers")


class TeacherViewSet(StandardTeamScopedCrudViewSet):
    """CRUD API for teachers."""

    queryset = Teacher.objects.all().order_by(Lower("name"), "id")
    serializer_class = TeacherSerializer
