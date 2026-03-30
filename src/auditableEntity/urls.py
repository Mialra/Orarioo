from django.urls import path

from auditableEntity.views import AuditEntryViewSet

audit_entry_list = AuditEntryViewSet.as_view({"get": "list"})
audit_entry_export = AuditEntryViewSet.as_view({"get": "export"})
audit_entry_filter_users = AuditEntryViewSet.as_view({"get": "filter_users"})

urlpatterns = [
    path("audit-entries/", audit_entry_list, name="auditentry-list"),
    path("audit-entries/export/", audit_entry_export, name="auditentry-export"),
    path("audit-entries/filter-users/", audit_entry_filter_users, name="auditentry-filter-users"),
]
