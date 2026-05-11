"""
Shared admin-page and simple CRUD view helpers.
"""

from rest_framework.response import Response

from common.drf import StandardPagination, TeamScopedAuditableModelViewSet
from main.views import render_admin_dashboard


def build_admin_tab_view(admin_tab):
    """Return a view function that renders the administration dashboard at the given tab."""

    def admin_view(request):
        """Render the administration dashboard with the configured tab selected."""
        return render_admin_dashboard(request, admin_tab)

    admin_view.__name__ = f"admin_{admin_tab}"
    return admin_view


class StandardTeamScopedCrudViewSet(TeamScopedAuditableModelViewSet):
    """Default base viewset for simple team-scoped CRUD modules."""

    pagination_class = StandardPagination
    summary_option_fields = ("name",)

    def get_summary_mode(self):
        """Return the requested lightweight summary mode for list endpoints.
        Input: self.request - DRF request with optional ?summary=<mode>
        Output: lowercase summary mode string, or empty string when not requested
        """
        return (self.request.query_params.get("summary") or "").strip().lower()

    def get_summary_options(self, queryset):
        """Return lightweight option rows for select-like consumers.
        Input: queryset - filtered team-scoped queryset
        Output: list of dicts containing id plus the configured summary fields
        """
        option_fields = ("id", *self.summary_option_fields)
        return list(queryset.values(*option_fields))

    def list(self, request, *args, **kwargs):
        """Serve paginated CRUD lists or lightweight summary payloads.
        Input: request - DRF request with optional ?summary=count|options
        Output: paginated Response, count payload, or options array
        """
        queryset = self.filter_queryset(self.get_queryset())
        summary_mode = self.get_summary_mode()

        if summary_mode == "count":
            return Response({"count": queryset.count()})

        if summary_mode == "options":
            return Response(self.get_summary_options(queryset))

        return super().list(request, *args, **kwargs)
