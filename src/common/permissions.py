from rest_framework import permissions


class IsManagementUser(permissions.BasePermission):
    """Allow access to authenticated users."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
