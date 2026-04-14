"""
Custom JWT authentication backend.
Extends SimpleJWT to reject tokens belonging to disabled or deleted users.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class ActiveUserJWTAuthentication(JWTAuthentication):
    """Reject JWTs for disabled or permanently deleted users."""

    def get_user(self, validated_token):
        """Resolve the user from a validated token and enforce active-account status.
        Input: validated_token - a verified SimpleJWT token object
        Output: User instance if active; raises AuthenticationFailed otherwise
        """
        user = super().get_user(validated_token)
        if not user.is_enabled or getattr(user, "deleted_at", None):
            raise AuthenticationFailed("This user account is no longer active.")
        return user
