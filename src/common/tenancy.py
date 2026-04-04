from rest_framework.exceptions import PermissionDenied

from user.models import CollaborationTeam


def get_active_team(request):
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
        team_name_seed = (getattr(user, "name", "") or "").strip() or user.email
        team = CollaborationTeam.objects.create(name=f"Equipo de {team_name_seed}")
        team.members.add(user)
        user.active_team = team
        user.save(update_fields=["active_team"])

    return team


def user_team_queryset(user):
    return CollaborationTeam.objects.filter(members=user).order_by("name", "id")
