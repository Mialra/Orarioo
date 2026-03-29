from django.urls import path

from auditableEntity.views import AuditEntryViewSet

audit_entry_list = AuditEntryViewSet.as_view({"get": "list"})

urlpatterns = [
    path("audit-entries/", audit_entry_list, name="auditentry-list"),
]
