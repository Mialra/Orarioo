"""
Shared admin-page and simple CRUD view helpers.
"""

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
