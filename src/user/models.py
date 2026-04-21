"""
Domain models for users, collaboration teams, team invitations, and data-export audit logs.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from namedEntity.models import NamedEntity


class CustomUserManager(BaseUserManager):
    """Custom manager for the User model that uses email as the primary identifier."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and persist a regular user with the given email and password.
        Input: email - str user email; password - str plain-text password or None; **extra_fields - additional model fields
        Output: User instance saved to the database; raises ValueError if email or name is missing
        """
        if not email:
            raise ValueError(_("Email is required"))

        # Backward compatibility while moving from given_name to name.
        if "name" not in extra_fields and "given_name" in extra_fields:
            extra_fields["name"] = extra_fields.pop("given_name")

        # Backward compatibility while removing role-based user management.
        extra_fields.pop("role", None)

        if not extra_fields.get("name"):
            raise ValueError(_("Name is required"))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and persist a superuser with is_staff and is_superuser set to True.
        Input: email - str user email; password - str plain-text password or None; **extra_fields - additional model fields
        Output: User instance with superuser privileges; raises ValueError if staff/superuser flags are unset
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True"))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True"))

        return self.create_user(email, password, **extra_fields)


class User(NamedEntity, AbstractUser):
    """Custom User model that uses email as the login identifier instead of username."""

    username = None
    password = models.CharField(
        _("password"),
        max_length=128,
        null=True,
        blank=True,
        help_text=_("User password hash or NULL after irreversible account deletion"),
    )
    email = models.EmailField(
        _("email"), unique=True, help_text=_("Unique email address")
    )
    family_name = models.CharField(
        max_length=150,
        blank=True,
        db_column="apellidos",
        help_text=_("User's family name"),
    )
    active_team = models.ForeignKey(
        "user.CollaborationTeam",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_users",
        help_text=_("Current collaboration team used as tenant context"),
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
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Permanent account deletion timestamp"),
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
            models.Index(fields=["is_enabled"]),
        ]

    def __str__(self):
        """Return a human-readable representation including the user's full name and email.
        Input: self - User instance
        Output: str in the format 'name family_name (email)'
        """
        return f"{self.name} {self.family_name} ({self.email})"

    @property
    def given_name(self):
        """Alias for the name field kept for backward compatibility.
        Input: self - User instance
        Output: str value of the name field
        """
        return self.name

    @given_name.setter
    def given_name(self, value):
        """Set the name field via the given_name alias.
        Input: self - User instance; value - str new name
        Output: None; side-effect: updates self.name
        """
        self.name = value

    def get_full_name(self):
        """Return the user's full name by combining name and family_name.
        Input: self - User instance
        Output: str full name with leading/trailing whitespace stripped
        """
        return f"{self.name} {self.family_name}".strip()


class CollaborationTeam(NamedEntity):
    """Group of users that share audit visibility scope."""

    members = models.ManyToManyField(
        User,
        related_name="collaboration_teams",
        blank=True,
    )

    class Meta:
        db_table = "collaboration_team"
        ordering = ["name", "id"]

    def __str__(self):
        """Return the collaboration team's name as its string representation.
        Input: self - CollaborationTeam instance
        Output: str team name
        """
        return self.name


class CollaborationTeamInvitationStatus(models.TextChoices):
    """Possible states for a collaboration team invitation."""

    PENDING = "pending", _("Pending")
    ACCEPTED = "accepted", _("Accepted")
    REJECTED = "rejected", _("Rejected")


class CollaborationTeamInvitation(models.Model):
    """Invitation record linking a user to a collaboration team with a pending/accepted/rejected status."""

    team = models.ForeignKey(
        CollaborationTeam,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    invited_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="team_invitations",
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_team_invitations",
    )
    status = models.CharField(
        max_length=20,
        choices=CollaborationTeamInvitationStatus.choices,
        default=CollaborationTeamInvitationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "collaboration_team_invitation"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["invited_user", "status"]),
            models.Index(fields=["team", "invited_user", "status"]),
        ]

    def __str__(self):
        """Return a human-readable summary of the invitation.
        Input: self - CollaborationTeamInvitation instance
        Output: str in the format 'invited_email -> team_name (status)'
        """
        return f"{self.invited_user.email} -> {self.team.name} ({self.status})"


class UserDataExportLog(models.Model):
    """Audit log for GDPR personal-data export requests."""

    class Outcome(models.TextChoices):
        """Possible results of a data-export attempt."""

        SUCCESS = "success", _("Success")
        RATE_LIMITED = "rate_limited", _("Rate limited")
        ERROR = "error", _("Error")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="data_export_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=512, blank=True)
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.SUCCESS,
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "user_data_export_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["outcome", "created_at"]),
        ]

    def __str__(self):
        """Return a human-readable summary of the export log entry.
        Input: self - UserDataExportLog instance
        Output: str in the format 'email - outcome - timestamp'
        """
        return f"{self.user.email} - {self.outcome} - {self.created_at.isoformat()}"
