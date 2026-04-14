from rest_framework import permissions, viewsets
from rest_framework.pagination import PageNumberPagination

from auditableEntity.audit import audit_actor_context
from common.tenancy import get_active_team

class StandardPagination(PageNumberPagination):
    page_size = 9
    page_size_query_param = "page_size"
    max_page_size = 100


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


class AuditActorViewMixin:
    _audit_actor_scope = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        actor = (
            request.user if getattr(request.user, "is_authenticated", False) else None
        )
        self._audit_actor_scope = audit_actor_context(user=actor)
        self._audit_actor_scope.__enter__()

    def finalize_response(self, request, response, *args, **kwargs):
        try:
            return super().finalize_response(request, response, *args, **kwargs)
        finally:
            if self._audit_actor_scope is not None:
                self._audit_actor_scope.__exit__(None, None, None)
                self._audit_actor_scope = None


class AuditableModelViewSet(AuditActorViewMixin, viewsets.ModelViewSet):
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


class TeamScopedAuditableModelViewSet(AuditableModelViewSet):
    """Auditable viewset scoped to the current active team."""

    team_field_name = "team"

    def get_active_team(self):
        return get_active_team(self.request)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.team_field_name: self.get_active_team()})

    def perform_create(self, serializer):
        actor = self._actor_email(self.request)
        serializer.save(
            **{
                self.team_field_name: self.get_active_team(),
                "created_by": actor,
                "updated_by": actor,
            }
        )
