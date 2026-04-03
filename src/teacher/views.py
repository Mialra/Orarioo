from common.drf import AuditableModelViewSet
from main.views import render_admin_dashboard
from teacher.models import Teacher
from teacher.serializers import TeacherSerializer


def admin_teachers(request):
    return render_admin_dashboard(request, "teachers")


class TeacherViewSet(AuditableModelViewSet):
    """CRUD API for teachers."""

    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
