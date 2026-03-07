from django.urls import path

from group.views import GroupViewSet

group_list = GroupViewSet.as_view({"get": "list", "post": "create"})
group_detail = GroupViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("groups/", group_list, name="group-list"),
    path("groups/<int:pk>/", group_detail, name="group-detail"),
]
