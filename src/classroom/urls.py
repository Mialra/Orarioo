from django.urls import path

from classroom.views import ClassroomViewSet

classroom_list = ClassroomViewSet.as_view({"get": "list", "post": "create"})
classroom_detail = ClassroomViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("classrooms/", classroom_list, name="classroom-list"),
    path("classrooms/<int:pk>/", classroom_detail, name="classroom-detail"),
]
