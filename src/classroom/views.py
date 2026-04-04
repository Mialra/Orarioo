from rest_framework.pagination import PageNumberPagination

from classroom.models import Classroom
from classroom.serializers import ClassroomSerializer
from common.drf import AuditableModelViewSet
from main.views import render_admin_dashboard


def admin_classrooms(request):
    return render_admin_dashboard(request, "classrooms")


class ClassroomViewSet(AuditableModelViewSet):
    """CRUD API for classrooms."""

    class ClassroomPagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = "page_size"
        max_page_size = 100

    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    pagination_class = ClassroomPagination
