"""
CRUD routes for teacher administration endpoints.
"""

from django.urls import path

from common.drf import build_crud_views
from teacher.views import TeacherViewSet

teacher_list, teacher_detail = build_crud_views(TeacherViewSet)

urlpatterns = [
    path("teachers/", teacher_list, name="teacher-list"),
    path("teachers/<int:pk>/", teacher_detail, name="teacher-detail"),
]
