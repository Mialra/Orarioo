"""
Root URL configuration for the Orarioo project.
Maps top-level paths to the admin panel and each application's URL module.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("main.urls")),
    path("api/", include("user.urls")),
    path("api/", include("auditableEntity.urls")),
    path("api/", include("teacher.urls")),
    path("api/", include("classroom.urls")),
    path("api/", include("group.urls")),
    path("api/", include("subject.urls")),
    path("api/", include("schedule.urls")),
]
