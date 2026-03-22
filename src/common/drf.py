from rest_framework import permissions, viewsets

CRUD_LIST_ACTIONS = {"get": "list", "post": "create"}
CRUD_DETAIL_ACTIONS = {
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
}


def build_crud_views(viewset_class):
    """Return list/detail DRF views for standard CRUD endpoints."""

    return (
        viewset_class.as_view(CRUD_LIST_ACTIONS),
        viewset_class.as_view(CRUD_DETAIL_ACTIONS),
    )


class AuditableModelViewSet(viewsets.ModelViewSet):
    """Base ViewSet that populates audit fields from authenticated user."""

    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _actor_email(request):
        return getattr(request.user, "email", "")

    def perform_create(self, serializer):
        actor = self._actor_email(self.request)
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        actor = self._actor_email(self.request)
        serializer.save(updated_by=actor)
