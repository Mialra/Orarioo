from rest_framework import permissions

from user.models import RoleChoices


class IsManagementUser(permissions.BasePermission):
    """Allow access to administrator and direccion roles."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in [RoleChoices.ADMINISTRATOR, RoleChoices.DIRECCION]
        )
