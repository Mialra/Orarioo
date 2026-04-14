from django.db.models.functions import Lower

from common.drf import StandardPagination, TeamScopedAuditableModelViewSet
from main.views import render_admin_dashboard
from teacher.models import Teacher
from teacher.serializers import TeacherSerializer


def admin_teachers(request):
    return render_admin_dashboard(request, "teachers")


class TeacherViewSet(TeamScopedAuditableModelViewSet):
    """CRUD API for teachers."""

    queryset = Teacher.objects.all().order_by(Lower("name"), "id")
    serializer_class = TeacherSerializer
    pagination_class = StandardPagination
