from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from namedEntity.models import NamedEntity


class RoleChoices(models.TextChoices):
    ADMINISTRATOR = "administrator", _("Administrator")
    DIRECCION = "direccion", _("Direccion")


class CustomUserManager(BaseUserManager):
    """Custom manager for User model"""

    def create_user(self, email, password=None, **extra_fields):
        """Creates and saves a user with the given email and password"""
        if not email:
            raise ValueError(_("Email is required"))

        # Backward compatibility while moving from given_name to name.
        if "name" not in extra_fields and "given_name" in extra_fields:
            extra_fields["name"] = extra_fields.pop("given_name")

        if not extra_fields.get("name"):
            raise ValueError(_("Name is required"))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Creates and saves a superuser"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", RoleChoices.ADMINISTRATOR)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True"))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True"))

        return self.create_user(email, password, **extra_fields)


class User(NamedEntity, AbstractUser):
    """Custom User model with differentiated roles"""

    username = None
    email = models.EmailField(
        _("email"), unique=True, help_text=_("Unique email address")
    )
    family_name = models.CharField(
        max_length=150,
        blank=True,
        db_column="apellidos",
        help_text=_("User's family name"),
    )
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.DIRECCION,
        help_text=_("User role in the system"),
    )
    is_enabled = models.BooleanField(
        default=True, db_column="activo", help_text=_("Indicates if the user is active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True, db_column="fecha_creacion", help_text=_("User creation date")
    )
    updated_at = models.DateTimeField(
        auto_now=True, db_column="fecha_actualizacion", help_text=_("Last update date")
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        db_table = "user"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_enabled"]),
        ]

    def __str__(self):
        return f"{self.name} {self.family_name} ({self.email})"

    @property
    def given_name(self):
        return self.name

    @given_name.setter
    def given_name(self, value):
        self.name = value

    def get_full_name(self):
        """Returns the user's full name"""
        return f"{self.name} {self.family_name}".strip()

    def is_administrator(self):
        """Checks if the user is an administrator"""
        return self.role == RoleChoices.ADMINISTRATOR

    def is_direccion(self):
        """Checks if the user is direccion"""
        return self.role == RoleChoices.DIRECCION
