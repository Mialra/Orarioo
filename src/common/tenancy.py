"""
Team resolution utilities for multi-tenant request handling.
Resolves the active CollaborationTeam for any authenticated request.
"""

from rest_framework.exceptions import PermissionDenied

from user.models import CollaborationTeam


def _create_default_team(user):
    """Create and assign a default CollaborationTeam for a user who has no teams yet.
    Input: user - an authenticated User instance with no existing collaboration teams
    Output: the newly created and persisted CollaborationTeam instance
    """
    name_seed = (getattr(user, "name", "") or "").strip() or user.email
    team = CollaborationTeam.objects.create(name=f"Equipo de {name_seed}")
    team.members.add(user)
    user.active_team = team
    user.save(update_fields=["active_team"])
    return team


def get_active_team(request):
    """Resolve the active CollaborationTeam for the current request.
    Input: request - an authenticated HTTP request with a User attached
    Output: CollaborationTeam instance; raises PermissionDenied if unauthenticated or team is invalid
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication is required.")

    active_team = getattr(user, "active_team", None)
    if active_team is not None:
        if user.collaboration_teams.filter(id=active_team.id).exists():
            return active_team
        raise PermissionDenied("The active team is not available for this user.")

    team = user.collaboration_teams.order_by("name", "id").first()
    if team is None:
        team = _create_default_team(user)

    return team


def user_team_queryset(user):
    """Return an ordered queryset of all teams the user belongs to.
    Input: user - a User instance
    Output: QuerySet of CollaborationTeam ordered by name then id
    """
    return CollaborationTeam.objects.filter(members=user).order_by("name", "id")
