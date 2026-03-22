from django.urls import path

from common.drf import build_crud_views
from group.views import GroupViewSet

group_list, group_detail = build_crud_views(GroupViewSet)

urlpatterns = [
    path("groups/", group_list, name="group-list"),
    path("groups/<int:pk>/", group_detail, name="group-detail"),
]
