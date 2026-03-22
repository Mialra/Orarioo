from common.drf import AuditableModelViewSet

from subject.models import Subject
from subject.serializers import SubjectSerializer


class SubjectViewSet(AuditableModelViewSet):
    """CRUD API for subjects."""

    queryset = Subject.objects.all().select_related("teacher", "group")
    serializer_class = SubjectSerializer
