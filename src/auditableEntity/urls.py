"""
Read-only routes for audit history listing and export endpoints.
"""

from django.urls import path

from auditableEntity.views import AuditEntryViewSet


def _build_audit_view(actions):
    """Bind an AuditEntryViewSet action mapping into a Django view callable."""
    return AuditEntryViewSet.as_view(actions)


audit_entry_list = _build_audit_view({"get": "list"})
audit_entry_export = _build_audit_view({"get": "export"})
audit_entry_filter_users = _build_audit_view({"get": "filter_users"})

urlpatterns = [
    path("audit-entries/", audit_entry_list, name="auditentry-list"),
    path("audit-entries/export/", audit_entry_export, name="auditentry-export"),
    path(
        "audit-entries/filter-users/",
        audit_entry_filter_users,
        name="auditentry-filter-users",
    ),
]
