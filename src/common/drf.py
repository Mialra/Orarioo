"""
Shared DRF base classes and utilities: pagination, audit viewsets, and CRUD route helpers.
"""

from rest_framework import permissions, viewsets
from rest_framework.pagination import PageNumberPagination

from auditableEntity.audit import audit_actor_context
from common.tenancy import get_active_team


class StandardPagination(PageNumberPagination):
    """Default paginator used across list endpoints (9 items per page)."""

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
    """Return the list and detail DRF view functions for standard CRUD endpoints.
    Input: viewset_class - a ModelViewSet subclass to bind actions to
    Output: tuple of (list_view, detail_view) callables
    """
    return (
        viewset_class.as_view(CRUD_LIST_ACTIONS),
        viewset_class.as_view(CRUD_DETAIL_ACTIONS),
    )


class AuditActorViewMixin:
    """Mixin that opens an audit-actor context for the duration of each request."""

    _audit_actor_scope = None

    def initial(self, request, *args, **kwargs):
        """Activate the audit-actor context before the view handler runs.
        Input: request - the incoming HTTP request
        Output: None; sets self._audit_actor_scope as a side effect
        """
        super().initial(request, *args, **kwargs)
        actor = (
            request.user if getattr(request.user, "is_authenticated", False) else None
        )
        self._audit_actor_scope = audit_actor_context(user=actor)
        self._audit_actor_scope.__enter__()

    def finalize_response(self, request, response, *args, **kwargs):
        """Close the audit-actor context after the response is built.
        Input: request, response - standard DRF finalize_response arguments
        Output: response after the audit context has been closed
        """
        try:
            return super().finalize_response(request, response, *args, **kwargs)
        finally:
            if self._audit_actor_scope is not None:
                self._audit_actor_scope.__exit__(None, None, None)
                self._audit_actor_scope = None


class AuditableModelViewSet(AuditActorViewMixin, viewsets.ModelViewSet):
    """Base ViewSet that populates audit fields (created_by/updated_by) from the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _actor_email(request):
        """Extract the email address of the authenticated user from the request.
        Input: request - the incoming HTTP request
        Output: str email address, or empty string if unavailable
        """
        return getattr(request.user, "email", "")

    def perform_create(self, serializer):
        """Save a new instance with both created_by and updated_by set to the actor's email.
        Input: serializer - a validated DRF serializer ready to save
        Output: None; saves the instance as a side effect
        """
        actor = self._actor_email(self.request)
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        """Save an updated instance with updated_by set to the actor's email.
        Input: serializer - a validated DRF serializer ready to save
        Output: None; saves the instance as a side effect
        """
        actor = self._actor_email(self.request)
        serializer.save(updated_by=actor)


class TeamScopedAuditableModelViewSet(AuditableModelViewSet):
    """Auditable viewset that automatically filters querysets to the active team."""

    team_field_name = "team"

    def get_active_team(self):
        """Resolve the active CollaborationTeam for the current request.
        Input: self.request - the incoming HTTP request
        Output: CollaborationTeam instance
        """
        return get_active_team(self.request)

    def get_queryset(self):
        """Return the base queryset filtered to the active team.
        Input: None (uses self.request implicitly via get_active_team)
        Output: QuerySet scoped to the active team
        """
        queryset = super().get_queryset()
        return queryset.filter(**{self.team_field_name: self.get_active_team()})

    def perform_create(self, serializer):
        """Save a new instance linked to the active team and audit-stamped with the actor's email.
        Input: serializer - a validated DRF serializer ready to save
        Output: None; saves the instance as a side effect
        """
        actor = self._actor_email(self.request)
        serializer.save(
            **{
                self.team_field_name: self.get_active_team(),
                "created_by": actor,
                "updated_by": actor,
            }
        )
