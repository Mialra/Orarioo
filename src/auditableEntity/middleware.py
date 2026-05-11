"""
Middleware that propagates the authenticated user into the audit context.
"""

from auditableEntity.audit import audit_actor_context


class AuditActorMiddleware:
    """Propagate authenticated user into audit context for every request."""

    def __init__(self, get_response):
        """Store the next middleware or view callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Execute the request within the matching audit actor context."""
        actor = (
            request.user if getattr(request.user, "is_authenticated", False) else None
        )
        with audit_actor_context(user=actor):
            return self.get_response(request)
