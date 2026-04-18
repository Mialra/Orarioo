"""
Serializers for user registration, authentication, profile updates, and collaboration team operations.
"""

import re

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from app.constants import STRING_MAX_LENGTH
from common.validators import (
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
    """Read-only serializer for embedding collaboration team id and name in other responses."""

    class Meta:
        model = CollaborationTeam
        fields = ["id", "name"]
        read_only_fields = fields


class CollaborationTeamCreateSerializer(serializers.Serializer):
    """Validate the name field when creating a new collaboration team."""

    name = serializers.CharField(max_length=STRING_MAX_LENGTH)

    def validate_name(self, value):
        """Normalize and validate the team name.
        Input: value - str submitted team name
        Output: str normalized name; raises ValidationError if blank or too long
        """
        return validate_and_normalize_required_text(
            value,
            field_name="name",
            label="name",
            max_length=STRING_MAX_LENGTH,
        )


class CollaborationTeamInviteSerializer(serializers.Serializer):
    """Validate the email and optional team_id when inviting a user to a team."""

    email = serializers.EmailField()
    team_id = serializers.IntegerField(required=False)

    def validate_email(self, value):
        """Normalize and validate the invitee email address.
        Input: value - str submitted email
        Output: str normalized email; raises ValidationError on invalid format
        """
        return validate_and_normalize_email(
            value,
            field_name="email",
            label="email",
        )


class CollaborationTeamInvitationSerializer(serializers.ModelSerializer):
    """Read-only serializer for displaying a collaboration team invitation with sender details."""

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
    """Validate the accept/reject action when a user responds to a team invitation."""

    action = serializers.ChoiceField(choices=["accept", "reject"])

    def to_status(self):
        """Map the validated action string to the corresponding invitation status value.
        Input: self - serializer with validated_data populated
        Output: CollaborationTeamInvitationStatus.ACCEPTED or REJECTED
        """
        action = self.validated_data["action"]
        if action == "accept":
            return CollaborationTeamInvitationStatus.ACCEPTED
        return CollaborationTeamInvitationStatus.REJECTED


class UserNameEmailValidationMixin:
    """Shared validation logic for user name and email fields across create/update serializers."""

    @staticmethod
    def validate_given_name(value):
        """Normalize and validate the given name field.
        Input: value - str submitted given name
        Output: str normalized name; raises ValidationError if blank or too long
        """
        return validate_and_normalize_required_text(
            value,
            field_name="given_name",
            label="given_name",
            max_length=STRING_MAX_LENGTH,
        )

    @staticmethod
    def validate_family_name(value):
        """Normalize the optional family name field.
        Input: value - str submitted family name (may be blank)
        Output: str normalized family name, or empty string
        """
        return normalize_optional_text(
            value,
            field_name="family_name",
            label="family_name",
            max_length=STRING_MAX_LENGTH,
        )

    def validate_email(self, value):
        """Normalize and enforce case-insensitive uniqueness for the email field.
        Input: value - str submitted email address
        Output: str normalized email; raises ValidationError if format is invalid or email is already taken
        """
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
    """Read/write serializer for displaying and updating user profile information."""

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
    """Validate and create a new user account, enforcing password strength and policy acceptance."""

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
        """Enforce password strength rules, confirm match, and require policy acceptance.
        Input: data - dict of deserialized field values
        Output: dict validated data; raises ValidationError on any password or policy violation
        """
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
        """Create a new User instance, stripping write-only confirmation fields before saving.
        Input: validated_data - dict of cleaned field values
        Output: User instance persisted to the database
        """
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")
        validated_data.pop("privacy_policy_accepted", None)
        validated_data.pop("terms_conditions_accepted", None)

        user = User.objects.create_user(**validated_data, password=password)
        return user


class UserUpdateSerializer(UserNameEmailValidationMixin, serializers.ModelSerializer):
    """Validate and apply partial updates to a user's profile fields."""

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
        """Apply profile field updates atomically.
        Input: instance - existing User instance; validated_data - dict of fields to update
        Output: User instance with updated fields saved to the database
        """
        return super().update(instance, validated_data)


class UserChangePasswordSerializer(serializers.Serializer):
    """Validate a password change request, checking the current password and confirming the new one."""

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
        """Ensure new_password and password_confirm match.
        Input: data - dict of deserialized field values
        Output: dict validated data; raises ValidationError if passwords do not match
        """
        if data["new_password"] != data["password_confirm"]:
            raise_validation_error(
                "password_confirm",
                "PASSWORD_MISMATCH",
                "New passwords do not match.",
                context={"field": "password_confirm"},
            )
        return data

    def validate_current_password(self, value):
        """Verify that the submitted current password matches the user's stored password.
        Input: value - str submitted current password
        Output: str validated value; raises ValidationError if password is incorrect
        """
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
        """Persist the new password to the database.
        Input: self - serializer with validated_data populated
        Output: User instance with the updated password saved
        """
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class UserAccountDeletionSerializer(serializers.Serializer):
    """Validate the self-service account deletion payload by requiring email confirmation."""

    confirmation_text = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Type the user's email address to confirm permanent deletion.",
    )

    def validate(self, data):
        """Ensure confirmation_text matches the requesting user's current email address.
        Input: data - dict with confirmation_text
        Output: dict validated data; raises ValidationError if confirmation does not match
        """
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
    """Validate login credentials and attach the authenticated User instance to validated_data."""

    email = serializers.EmailField(help_text="User's email address")
    password = serializers.CharField(write_only=True, help_text="User's password")

    def validate(self, data):
        """Verify email and password, check account status, and attach the user to validated_data.
        Input: data - dict with email and password
        Output: dict with added 'user' key on success; raises ValidationError on bad credentials or disabled account
        """
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
