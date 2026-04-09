from django.urls import path

from classroom.views import admin_classrooms
from group.views import admin_groups
from main.views import dashboard, privacy_policy, root_redirect
from subject.views import admin_subjects
from teacher.views import admin_teachers
from user.views import admin_users, sign_in, sign_up

urlpatterns = [
    path("", root_redirect, name="root-redirect"),
    path("sign-in/", sign_in, name="sign-in"),
    path("sign-up/", sign_up, name="sign-up"),
    path("privacy-policy/", privacy_policy, name="privacy-policy"),
    path("dashboard/", dashboard, {"section": "schedules"}, name="dashboard"),
    path(
        "dashboard/schedules/",
        dashboard,
        {"section": "schedules"},
        name="dashboard-schedules",
    ),
    path("dashboard/saved/", dashboard, {"section": "saved"}, name="dashboard-saved"),
    path(
        "dashboard/saved/<path:timetable_name>/",
        dashboard,
        {"section": "saved"},
        name="dashboard-saved-detail",
    ),
    path("dashboard/administration/", admin_users, name="dashboard-administration"),
    path(
        "dashboard/administration/users/",
        admin_users,
        name="dashboard-administration-users",
    ),
    path(
        "dashboard/administration/teachers/",
        admin_teachers,
        name="dashboard-administration-teachers",
    ),
    path(
        "dashboard/administration/groups/",
        admin_groups,
        name="dashboard-administration-groups",
    ),
    path(
        "dashboard/administration/subjects/",
        admin_subjects,
        name="dashboard-administration-subjects",
    ),
    path(
        "dashboard/administration/classrooms/",
        admin_classrooms,
        name="dashboard-administration-classrooms",
    ),
    path("dashboard/audit/", dashboard, {"section": "audit"}, name="dashboard-audit"),
]
