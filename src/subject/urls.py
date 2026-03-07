from django.urls import path

from subject.views import SubjectViewSet

subject_list = SubjectViewSet.as_view({"get": "list", "post": "create"})
subject_detail = SubjectViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("subjects/", subject_list, name="subject-list"),
    path("subjects/<int:pk>/", subject_detail, name="subject-detail"),
]
