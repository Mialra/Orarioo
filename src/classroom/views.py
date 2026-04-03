from classroom.models import Classroom
from classroom.serializers import ClassroomSerializer
from common.drf import AuditableModelViewSet
from main.views import render_admin_dashboard


def admin_classrooms(request):
    return render_admin_dashboard(request, "classrooms")


class ClassroomViewSet(AuditableModelViewSet):
    """CRUD API for classrooms."""

    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
