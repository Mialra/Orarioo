"""
Top-level URL configuration: auth, dashboard, administration tabs, and legal pages.
"""

from django.urls import path

from classroom.views import admin_classrooms
from common.admin import build_admin_tab_view
from group.views import admin_groups
from main.views import (
    dashboard,
    onboarding,
    privacy_policy,
    root_redirect,
    security_protocol,
    terms_and_conditions,
)
from main.views_manual import UserManualPDFView
from subject.views import admin_subjects
from teacher.views import admin_teachers
from user.views import admin_users, sign_in, sign_up
from user.views_export import ProfileExportDataView, profile

urlpatterns = [
    path("", root_redirect, name="root-redirect"),
    path("sign-in/", sign_in, name="sign-in"),
    path("sign-up/", sign_up, name="sign-up"),
    path("profile/", profile, name="profile"),
    path(
        "profile/export-data/",
        ProfileExportDataView.as_view(),
        name="profile-export-data",
    ),
    path("privacy-policy/", privacy_policy, name="privacy-policy"),
    path("security-protocol/", security_protocol, name="security-protocol"),
    path(
        "terms-and-conditions/",
        terms_and_conditions,
        name="terms-and-conditions",
    ),
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
    path(
        "dashboard/administration/schedule-config/",
        build_admin_tab_view("schedule_config"),
        name="dashboard-administration-schedule-config",
    ),
    path("onboarding/", onboarding, name="onboarding"),
    path("manual/", UserManualPDFView.as_view(), name="user-manual"),
]
