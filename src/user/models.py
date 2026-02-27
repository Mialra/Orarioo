from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class RoleChoices(models.TextChoices):
    ADMINISTRATOR = "administrator", _("Administrator")
    DIRECTOR = "director", _("Director")


class CustomUserManager(BaseUserManager):
    """Custom manager for User model"""

    def create_user(self, email, password=None, **extra_fields):
        """Creates and saves a user with the given email and password"""
        if not email:
            raise ValueError(_("Email is required"))

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


class User(AbstractUser):
    """Custom User model with differentiated roles"""

    username = None
    email = models.EmailField(
        _("email"), unique=True, help_text=_("Unique email address")
    )
    given_name = models.CharField(
        max_length=150, db_column="nombre", help_text=_("User's given name")
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
        default=RoleChoices.DIRECTOR,
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
    REQUIRED_FIELDS = ["given_name"]

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
        return f"{self.given_name} {self.family_name} ({self.email})"

    def get_full_name(self):
        """Returns the user's full name"""
        return f"{self.given_name} {self.family_name}".strip()

    def is_administrator(self):
        """Checks if the user is an administrator"""
        return self.role == RoleChoices.ADMINISTRATOR

    def is_director(self):
        """Checks if the user is a director"""
        return self.role == RoleChoices.DIRECTOR
