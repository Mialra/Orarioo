from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class ActiveUserJWTAuthentication(JWTAuthentication):
    """Reject JWTs for disabled or permanently deleted users."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not user.is_enabled or getattr(user, "deleted_at", None):
            raise AuthenticationFailed("This user account is no longer active.")
        return user
