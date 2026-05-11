"""
Serializers for user registration, authentication, profile updates, and collaboration team operations.
"""

import re

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from app.constants import STRING_MAX_LENGTH
from common.errors import build_error_entry
from common.stages import DEFAULT_STAGE_COLORS, STAGE_COLOR_CHOICES
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


# ---------------------------------------------------------------------------
# Schedule configuration serializers
# ---------------------------------------------------------------------------


def _validate_hhmm(value, field_label):
    """Parse and validate a 'HH:MM' time string.
    Input: value - str to validate; field_label - name used in error messages
    Output: str value unchanged if valid; raises ValidationError otherwise
    """
    try:
        h, m = value.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        raise serializers.ValidationError(
            {field_label: f"'{value}' no es una hora válida en formato HH:MM."}
        )
    return value


def _schedule_config_error_entry(stage_code, error_payload):
    """Build a structured schedule-config validation entry from nested serializer errors."""

    raw_message = _first_error_message(error_payload)
    message = raw_message or "La configuración de los tramos no es válida."
    code = "INVALID_SCHEDULE_CONFIG"

    if (
        message
        == "El recreo debe estar dentro de la hora de entrada y salida de la etapa."
    ):
        code = "BREAK_OUTSIDE_STAGE_RANGE"
    elif message == "La hora de fin del recreo debe ser posterior a la hora de inicio.":
        code = "INVALID_BREAK_RANGE"
    elif message == "Los recreos no pueden solaparse entre sí.":
        code = "OVERLAPPING_BREAKS"
    elif message == "La hora de fin debe ser posterior a la hora de inicio.":
        code = "INVALID_TIME_RANGE"
    elif message == "La duración de la sesión debe ser exactamente de 60 minutos.":
        code = "INVALID_SESSION_DURATION"

    return build_error_entry(
        code,
        message,
        context={"stage": stage_code},
    )


def _first_error_message(value):
    """Return the first text message from a nested DRF error payload."""

    if isinstance(value, dict):
        if "message" in value:
            return str(value.get("message") or "")
        for nested_value in value.values():
            message = _first_error_message(nested_value)
            if message:
                return message
        return ""

    if isinstance(value, list):
        for item in value:
            message = _first_error_message(item)
            if message:
                return message
        return ""

    if value in (None, ""):
        return ""

    return str(value)


class StageConfigSerializer(serializers.Serializer):
    """Validate the schedule config for a single educational stage."""

    label = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=""
    )
    color = serializers.ChoiceField(
        choices=[(color, color) for color in STAGE_COLOR_CHOICES],
        required=False,
        default="blue",
    )
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    breaks = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        required=False,
        default=list,
    )
    session_duration = serializers.IntegerField(min_value=60, max_value=60, default=60)

    def validate(self, data):
        """Cross-field validation: start < end, each break has valid times within range, no overlap.
        Input: data - dict of field values
        Output: validated data dict; raises ValidationError on constraint violations
        """
        from datetime import time as dt_time

        def parse(v):
            h, m = v.split(":")
            return dt_time(int(h), int(m))

        start = parse(_validate_hhmm(data["start_time"], "start_time"))
        end = parse(_validate_hhmm(data["end_time"], "end_time"))
        if end <= start:
            raise serializers.ValidationError(
                {"end_time": "La hora de fin debe ser posterior a la hora de inicio."}
            )
        if int(data.get("session_duration", 60)) != 60:
            raise serializers.ValidationError(
                {
                    "session_duration": "La duración de la sesión debe ser exactamente de 60 minutos."
                }
            )

        breaks = data.get("breaks") or []
        parsed = []
        for i, b in enumerate(breaks):
            if "start" not in b or "end" not in b:
                raise serializers.ValidationError(
                    {
                        f"breaks[{i}]": "Cada recreo debe tener las claves 'start' y 'end'."
                    }
                )
            bs_t = parse(_validate_hhmm(b["start"], f"breaks[{i}].start"))
            be_t = parse(_validate_hhmm(b["end"], f"breaks[{i}].end"))
            if be_t <= bs_t:
                raise serializers.ValidationError(
                    {
                        f"breaks[{i}]": "La hora de fin del recreo debe ser posterior a la hora de inicio."
                    }
                )
            if bs_t < start or be_t > end:
                raise serializers.ValidationError(
                    {
                        f"breaks[{i}]": "El recreo debe estar dentro de la hora de entrada y salida de la etapa."
                    }
                )
            parsed.append((bs_t, be_t))

        # Check for overlaps between breaks
        parsed_sorted = sorted(parsed)
        for j in range(1, len(parsed_sorted)):
            if parsed_sorted[j][0] < parsed_sorted[j - 1][1]:
                raise serializers.ValidationError(
                    {"breaks": "Los recreos no pueden solaparse entre sí."}
                )

        return data


class ScheduleConfigSerializer(serializers.Serializer):
    """Validate a full schedule_config dict (stage_code → stage config)."""

    schedule_config = serializers.DictField(
        child=serializers.DictField(), required=True
    )

    def validate_schedule_config(self, value):
        """Ensure each stage config passes StageConfigSerializer.
        Input: value - dict {stage_code: {start_time, end_time, ...}}
        Output: validated dict; raises ValidationError on any violation
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "La configuración de tramos debe ser un objeto."
            )
        errors = {}
        validated = {}
        for stage, cfg in value.items():
            s = StageConfigSerializer(data=cfg)
            if not s.is_valid():
                errors[stage] = _schedule_config_error_entry(stage, s.errors)
                continue
            stage_cfg = dict(s.validated_data)
            stage_cfg["color"] = stage_cfg.get("color") or DEFAULT_STAGE_COLORS.get(
                stage, "blue"
            )
            validated[stage] = stage_cfg
        if errors:
            raise serializers.ValidationError(list(errors.values()))
        seen_labels = {}
        for stage_code, stage_cfg in validated.items():
            label = (stage_cfg.get("label") or "").strip().lower()
            if not label:
                continue
            if label in seen_labels:
                raise serializers.ValidationError(
                    f"El nombre de tramo '{stage_cfg['label']}' ya está en uso."
                )
            seen_labels[label] = stage_code
        return validated


class OnboardingSerializer(serializers.Serializer):
    """Validate onboarding payload: team name + optional schedule_config."""

    team_name = serializers.CharField(max_length=STRING_MAX_LENGTH)
    schedule_config = serializers.DictField(
        child=serializers.DictField(), required=False, default=dict
    )

    def validate_team_name(self, value):
        """Normalize and validate team name.
        Input: value - str submitted name
        Output: str normalized; raises ValidationError if blank
        """
        return validate_and_normalize_required_text(value, field_name="team_name")

    def validate_schedule_config(self, value):
        """Delegate to ScheduleConfigSerializer for stage-level validation.
        Input: value - raw schedule_config dict
        Output: validated dict
        """
        if not value:
            return value
        inner = ScheduleConfigSerializer(data={"schedule_config": value})
        if not inner.is_valid():
            raise serializers.ValidationError(
                inner.errors.get("schedule_config", inner.errors)
            )
        return inner.validated_data["schedule_config"]
