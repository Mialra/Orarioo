"""
CRUD routes for subject administration endpoints.
"""

from django.urls import path

from common.drf import build_crud_views
from subject.views import SubjectViewSet

subject_list, subject_detail = build_crud_views(SubjectViewSet)

urlpatterns = [
    path("subjects/", subject_list, name="subject-list"),
    path("subjects/<int:pk>/", subject_detail, name="subject-detail"),
]
