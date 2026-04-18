"""
Shared serializer mixins for team-scoped API modules.
"""

from rest_framework import serializers

from common.tenancy import get_active_team


class TeamScopedModelSerializerMixin:
    """Expose the read-only team field and scope related fields to the active team."""

    team = serializers.PrimaryKeyRelatedField(read_only=True)
    team_scoped_field_models = {}
    team_scoped_field_querysets = {}

    def __init__(self, *args, **kwargs):
        """Initialize the serializer and constrain configured relations to the active team."""
        super().__init__(*args, **kwargs)
        self._scope_related_fields_to_active_team()

    def _scope_related_fields_to_active_team(self):
        """Restrict configured serializer relations to the request's active team."""
        request = self.context.get("request")
        if not request or not getattr(request, "user", None):
            return

        active_team = get_active_team(request)

        for field_name, model in self.team_scoped_field_models.items():
            if field_name in self.fields:
                self.fields[field_name].queryset = model.objects.filter(
                    team=active_team
                )

        for field_name, queryset_factory in self.team_scoped_field_querysets.items():
            if field_name in self.fields:
                self.fields[field_name].queryset = queryset_factory(active_team)
