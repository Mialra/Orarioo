from auditableEntity.audit import audit_actor_context


class AuditActorMiddleware:
    """Propagate authenticated user into audit context for every request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        actor = (
            request.user if getattr(request.user, "is_authenticated", False) else None
        )
        with audit_actor_context(user=actor):
            return self.get_response(request)
