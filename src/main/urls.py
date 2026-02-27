from django.urls import path

from main.views import frontend_playground

urlpatterns = [
    path("", frontend_playground, name="frontend-playground"),
]
