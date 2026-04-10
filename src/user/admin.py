from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from user.models import CollaborationTeam, User, UserDataExportLog


@admin.register(User)
class UserAdmin(UserAdmin):
    """Custom configuration for user management in the admin panel"""

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal information"),
            {
                "fields": (
                    "name",
                    "family_name",
                )
            },
        ),
        (
            _("System information"),
            {
                "fields": (
                    "is_enabled",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("Important dates"),
            {"fields": ("last_login", "created_at", "updated_at")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
        (
            _("Personal information"),
            {
                "classes": ("wide",),
                "fields": ("name", "family_name"),
            },
        ),
        (
            _("Permissions"),
            {
                "classes": ("wide",),
                "fields": ("is_enabled", "is_staff", "is_superuser"),
            },
        ),
    )

    list_display = (
        "email",
        "name",
        "family_name",
        "is_enabled",
        "is_staff",
        "created_at",
    )
    list_filter = ("is_enabled", "is_staff", "is_superuser", "created_at")
    search_fields = ("email", "name", "family_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "last_login")

    filter_horizontal = ("groups", "user_permissions")

    def get_readonly_fields(self, request, obj=None):
        """Makes certain fields read-only"""
        if obj:  # When editing an existing user
            return self.readonly_fields + ("email",)
        return self.readonly_fields


@admin.register(CollaborationTeam)
class CollaborationTeamAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    filter_horizontal = ("members",)


@admin.register(UserDataExportLog)
class UserDataExportLogAdmin(admin.ModelAdmin):
    list_display = ("user", "outcome", "ip_address", "created_at")
    list_filter = ("outcome", "created_at")
    search_fields = ("user__email", "ip_address", "notes")
    readonly_fields = (
        "user",
        "created_at",
        "ip_address",
        "user_agent",
        "outcome",
        "notes",
    )
