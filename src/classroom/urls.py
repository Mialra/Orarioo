from django.urls import path

from common.drf import build_crud_views
from classroom.views import ClassroomViewSet

classroom_list, classroom_detail = build_crud_views(ClassroomViewSet)

urlpatterns = [
    path("classrooms/", classroom_list, name="classroom-list"),
    path("classrooms/<int:pk>/", classroom_detail, name="classroom-detail"),
]
