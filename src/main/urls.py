from django.urls import path

from main.views import frontend_playground, manual_change, schedule_generator

urlpatterns = [
    path("", frontend_playground, name="frontend-playground"),
    path("schedule-generator/", schedule_generator, name="schedule-generator"),
    path("manual-change/", manual_change, name="manual-change"),
]
