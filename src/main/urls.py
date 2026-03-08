from django.urls import path

from main.views import frontend_playground, schedule_generator

urlpatterns = [
    path("", frontend_playground, name="frontend-playground"),
    path("schedule-generator/", schedule_generator, name="schedule-generator"),
]
