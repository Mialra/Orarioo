from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from user.models import (
    CollaborationTeam,
    CollaborationTeamInvitation,
    CollaborationTeamInvitationStatus,
    User,
)


class CollaborationTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollaborationTeam
        fields = ["id", "name"]
        read_only_fields = fields


class CollaborationTeamCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)

    def validate_name(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Team name cannot be empty.")
        return normalized


class CollaborationTeamInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    team_id = serializers.IntegerField(required=False)


class CollaborationTeamInvitationSerializer(serializers.ModelSerializer):
    team = CollaborationTeamSerializer(read_only=True)
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)
    invited_by_name = serializers.CharField(source="invited_by.name", read_only=True)

    class Meta:
        model = CollaborationTeamInvitation
        fields = [
            "id",
            "team",
            "status",
            "invited_by_email",
            "invited_by_name",
            "created_at",
            "responded_at",
        ]
        read_only_fields = fields


class CollaborationTeamInvitationRespondSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["accept", "reject"])

    def to_status(self):
        action = self.validated_data["action"]
        if action == "accept":
            return CollaborationTeamInvitationStatus.ACCEPTED
        return CollaborationTeamInvitationStatus.REJECTED


class UserNameEmailValidationMixin:
    @staticmethod
    def validate_given_name(value):
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value

    def validate_email(self, value):
        queryset = User.objects.filter(email=value)
        if self.instance is not None:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("This email is already registered.")
        return value


class UserSerializer(serializers.ModelSerializer):
    """Serializer for displaying user information"""

    given_name = serializers.CharField(source="name")
    active_team = CollaborationTeamSerializer(read_only=True)
    collaboration_teams = CollaborationTeamSerializer(many=True, read_only=True)
    deleted_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "given_name",
            "family_name",
            "email",
            "deleted_at",
            "active_team",
            "collaboration_teams",
            "is_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserCreateSerializer(UserNameEmailValidationMixin, serializers.ModelSerializer):
    """Serializer for creating new users"""

    given_name = serializers.CharField(source="name")
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        help_text="User password",
    )
    password_confirm = serializers.CharField(
        write_only=True, required=True, help_text="Password confirmation"
    )
    privacy_policy_accepted = serializers.BooleanField(
        write_only=True,
        required=True,
        help_text="Privacy policy acceptance flag",
    )
    terms_conditions_accepted = serializers.BooleanField(
        write_only=True,
        required=True,
        help_text="Terms and conditions acceptance flag",
    )

    class Meta:
        model = User
        fields = [
            "given_name",
            "family_name",
            "email",
            "password",
            "password_confirm",
            "privacy_policy_accepted",
            "terms_conditions_accepted",
        ]

    def validate(self, data):
        """Validates that passwords match"""
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})

        if not data.get("privacy_policy_accepted"):
            raise serializers.ValidationError(
                {
                    "privacy_policy_accepted": (
                        "You must accept the privacy policy to complete signup."
                    )
                }
            )

        if not data.get("terms_conditions_accepted"):
            raise serializers.ValidationError(
                {
                    "terms_conditions_accepted": (
                        "You must accept the terms and conditions to complete signup."
                    )
                }
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        """Creates a new user"""
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")
        validated_data.pop("privacy_policy_accepted", None)
        validated_data.pop("terms_conditions_accepted", None)

        user = User.objects.create_user(**validated_data, password=password)
        return user


class UserUpdateSerializer(UserNameEmailValidationMixin, serializers.ModelSerializer):
    """Serializer for updating user information"""

    given_name = serializers.CharField(source="name")

    class Meta:
        model = User
        fields = [
            "given_name",
            "family_name",
            "email",
            "is_enabled",
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        """Updates user data atomically."""
        return super().update(instance, validated_data)


class UserChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""

    current_password = serializers.CharField(
        write_only=True, required=True, help_text="User's current password"
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        help_text="New password",
    )
    password_confirm = serializers.CharField(
        write_only=True, required=True, help_text="New password confirmation"
    )

    def validate(self, data):
        """Validates that the new passwords match"""
        if data["new_password"] != data["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "New passwords do not match."}
            )
        return data

    def validate_current_password(self, value):
        """Validates that the current password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def save(self):
        """Saves the new password"""
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class UserAccountDeletionSerializer(serializers.Serializer):
    """Validates the self-service account deletion payload."""

    confirmation_text = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Type the user's email address to confirm permanent deletion.",
    )

    def validate(self, data):
        user = self.context["request"].user
        expected_confirmation = (user.email or "").strip().lower()
        provided_confirmation = (data.get("confirmation_text") or "").strip().lower()

        if provided_confirmation != expected_confirmation:
            raise serializers.ValidationError(
                {
                    "confirmation_text": (
                        "Debes escribir exactamente tu correo electrónico para eliminar la cuenta."
                    )
                }
            )
        return data


class LoginSerializer(serializers.Serializer):
    """Serializer for authenticating users"""

    email = serializers.EmailField(help_text="User's email address")
    password = serializers.CharField(write_only=True, help_text="User's password")

    def validate(self, data):
        """Validates login credentials"""
        email = data.get("email")
        password = data.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Incorrect email or password.")

        if not user.check_password(password):
            raise serializers.ValidationError("Incorrect email or password.")

        if not user.is_enabled or getattr(user, "deleted_at", None):
            raise serializers.ValidationError("This user has been deactivated.")

        data["user"] = user
        return data
