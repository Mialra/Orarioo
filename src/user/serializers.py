import re

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from app.constants import STRING_MAX_LENGTH
from common.validators.validators import (
    normalize_optional_text,
    raise_non_field_error,
    raise_validation_error,
    validate_and_normalize_email,
    validate_and_normalize_required_text,
    validate_case_insensitive_unique,
)
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
    name = serializers.CharField(max_length=STRING_MAX_LENGTH)

    def validate_name(self, value):
        return validate_and_normalize_required_text(
            value,
            field_name="name",
            label="name",
            max_length=STRING_MAX_LENGTH,
        )


class CollaborationTeamInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    team_id = serializers.IntegerField(required=False)

    def validate_email(self, value):
        return validate_and_normalize_email(
            value,
            field_name="email",
            label="email",
        )


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
        return validate_and_normalize_required_text(
            value,
            field_name="given_name",
            label="given_name",
            max_length=STRING_MAX_LENGTH,
        )

    @staticmethod
    def validate_family_name(value):
        return normalize_optional_text(
            value,
            field_name="family_name",
            label="family_name",
            max_length=STRING_MAX_LENGTH,
        )

    def validate_email(self, value):
        normalized = validate_and_normalize_email(
            value,
            field_name="email",
            label="email",
        )
        return validate_case_insensitive_unique(
            normalized,
            field_name="email",
            queryset=User.objects.all(),
            instance=self.instance,
            label="email",
        )


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
    email = serializers.EmailField(validators=[])
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
        password = data.get("password") or ""

        if len(password) < 8:
            raise_validation_error(
                "password",
                "PASSWORD_MIN_LENGTH",
                "Password must be at least 8 characters long.",
                context={"field": "password", "min_length": 8},
            )

        if not re.search(r"[A-Za-z]", password):
            raise_validation_error(
                "password",
                "PASSWORD_REQUIRES_LETTER",
                "Password must include at least one letter.",
                context={"field": "password"},
            )

        if not re.search(r"\d", password):
            raise_validation_error(
                "password",
                "PASSWORD_REQUIRES_NUMBER",
                "Password must include at least one number.",
                context={"field": "password"},
            )

        if data["password"] != data["password_confirm"]:
            raise_validation_error(
                "password_confirm",
                "PASSWORD_MISMATCH",
                "Passwords do not match.",
                context={"field": "password_confirm"},
            )

        if not data.get("privacy_policy_accepted"):
            raise_validation_error(
                "privacy_policy_accepted",
                "POLICY_NOT_ACCEPTED",
                "You must accept the privacy policy to complete signup.",
                context={"field": "privacy_policy_accepted"},
            )

        if not data.get("terms_conditions_accepted"):
            raise_validation_error(
                "terms_conditions_accepted",
                "TERMS_NOT_ACCEPTED",
                "You must accept the terms and conditions to complete signup.",
                context={"field": "terms_conditions_accepted"},
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
            raise_validation_error(
                "password_confirm",
                "PASSWORD_MISMATCH",
                "New passwords do not match.",
                context={"field": "password_confirm"},
            )
        return data

    def validate_current_password(self, value):
        """Validates that the current password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise_validation_error(
                "current_password",
                "INVALID_CREDENTIALS",
                "Current password is incorrect.",
                context={"field": "current_password"},
            )
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
            raise_validation_error(
                "confirmation_text",
                "INVALID_CONFIRMATION_TEXT",
                "confirmation_text must exactly match the current email address.",
                context={"field": "confirmation_text"},
            )
        return data


class LoginSerializer(serializers.Serializer):
    """Serializer for authenticating users"""

    email = serializers.EmailField(help_text="User's email address")
    password = serializers.CharField(write_only=True, help_text="User's password")

    def validate(self, data):
        """Validates login credentials"""
        email = validate_and_normalize_email(
            data.get("email"),
            field_name="email",
            label="email",
        )
        password = data.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise_non_field_error(
                "INVALID_CREDENTIALS",
                "Incorrect email or password.",
            )

        if not user.check_password(password):
            raise_non_field_error(
                "INVALID_CREDENTIALS",
                "Incorrect email or password.",
            )

        if not user.is_enabled or getattr(user, "deleted_at", None):
            raise_non_field_error(
                "USER_DISABLED",
                "This user has been deactivated.",
            )

        data["user"] = user
        data["email"] = email
        return data
