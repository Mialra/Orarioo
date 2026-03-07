from django.urls import path

from teacher.views import TeacherViewSet

teacher_list = TeacherViewSet.as_view({"get": "list", "post": "create"})
teacher_detail = TeacherViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("teachers/", teacher_list, name="teacher-list"),
    path("teachers/<int:pk>/", teacher_detail, name="teacher-detail"),
]
