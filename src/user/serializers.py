from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from user.models import RoleChoices, User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for displaying user information"""

    given_name = serializers.CharField(source="name")
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "given_name",
            "family_name",
            "email",
            "role",
            "role_display",
            "is_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_role_display(self, obj):
        """Returns the readable representation of the role"""
        return obj.get_role_display()


class UserCreateSerializer(serializers.ModelSerializer):
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
    role = serializers.ChoiceField(
        choices=RoleChoices.choices,
        default=RoleChoices.DIRECTOR,
        help_text="User role (administrator, director)",
    )

    class Meta:
        model = User
        fields = [
            "given_name",
            "family_name",
            "email",
            "role",
            "password",
            "password_confirm",
        ]

    def validate(self, data):
        """Validates that passwords match"""
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def validate_email(self, value):
        """Validates that the email is unique"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_given_name(self, value):
        """Validates that the name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Creates a new user"""
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")

        user = User.objects.create_user(**validated_data, password=password)
        return user


class UserManagementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users from admin/direction panel with optional login."""

    given_name = serializers.CharField(source="name")
    role = serializers.ChoiceField(
        choices=RoleChoices.choices,
        default=RoleChoices.DIRECTOR,
        help_text="User role (administrator, director)",
    )
    can_login = serializers.BooleanField(default=False)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        validators=[validate_password],
        help_text="Optional password. Required only if can_login=true.",
    )

    class Meta:
        model = User
        fields = [
            "given_name",
            "family_name",
            "email",
            "role",
            "can_login",
            "password",
            "is_enabled",
        ]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_given_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value

    def validate(self, data):
        can_login = data.get("can_login", False)
        password = data.get("password", "")
        if can_login and not password:
            raise serializers.ValidationError(
                {"password": "Password is required when can_login is true."}
            )
        return data

    @transaction.atomic
    def create(self, validated_data):
        can_login = validated_data.pop("can_login", False)
        password = validated_data.pop("password", "")
        if not can_login:
            password = None
        user = User.objects.create_user(**validated_data, password=password)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information"""

    given_name = serializers.CharField(source="name")
    role = serializers.ChoiceField(choices=RoleChoices.choices, help_text="User role")

    class Meta:
        model = User
        fields = [
            "given_name",
            "family_name",
            "email",
            "role",
            "is_enabled",
        ]

    def validate_email(self, value):
        """Validates that the email is unique (excluding current user)"""
        user = self.instance
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_given_name(self, value):
        """Validates that the name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        """Updates user data"""
        instance.name = validated_data.get("name", instance.name)
        instance.family_name = validated_data.get("family_name", instance.family_name)
        instance.email = validated_data.get("email", instance.email)
        instance.role = validated_data.get("role", instance.role)
        instance.is_enabled = validated_data.get("is_enabled", instance.is_enabled)
        instance.save()
        return instance


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

        if not user.is_enabled:
            raise serializers.ValidationError("This user has been deactivated.")

        data["user"] = user
        return data
