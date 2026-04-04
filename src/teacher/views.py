from common.drf import AuditableModelViewSet
from django.db.models.functions import Lower
from main.views import render_admin_dashboard
from rest_framework.pagination import PageNumberPagination
from teacher.models import Teacher
from teacher.serializers import TeacherSerializer


def admin_teachers(request):
    return render_admin_dashboard(request, "teachers")


class TeacherViewSet(AuditableModelViewSet):
    """CRUD API for teachers."""

    class TeacherPagination(PageNumberPagination):
        page_size = 15
        page_size_query_param = "page_size"
        max_page_size = 100

    queryset = Teacher.objects.all().order_by(Lower("name"), "id")
    serializer_class = TeacherSerializer
    pagination_class = TeacherPagination
