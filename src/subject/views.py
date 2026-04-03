from common.drf import AuditableModelViewSet
from main.views import render_admin_dashboard
from subject.models import Subject
from subject.serializers import SubjectSerializer


def admin_subjects(request):
    return render_admin_dashboard(request, "subjects")


class SubjectViewSet(AuditableModelViewSet):
    """CRUD API for subjects."""

    queryset = Subject.objects.all().select_related("teacher", "group")
    serializer_class = SubjectSerializer
