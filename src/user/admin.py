"""
Django admin registration for users, collaboration teams, and data-export audit logs.
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from common.notifications import send_security_email
from securityIncident.models import SecurityIncident
from user.models import CollaborationTeam, User, UserDataExportLog


@admin.register(User)
class UserAdmin(UserAdmin):
    """Admin configuration for user management, including security breach notifications and account blocking."""

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal information"),
            {
                "fields": (
                    "name",
                    "family_name",
                )
            },
        ),
        (
            _("System information"),
            {
                "fields": (
                    "is_enabled",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("Important dates"),
            {"fields": ("last_login", "created_at", "updated_at", "deleted_at")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
        (
            _("Personal information"),
            {
                "classes": ("wide",),
                "fields": ("name", "family_name"),
            },
        ),
        (
            _("Permissions"),
            {
                "classes": ("wide",),
                "fields": ("is_enabled", "is_staff", "is_superuser"),
            },
        ),
    )

    list_display = (
        "email",
        "name",
        "family_name",
        "is_enabled",
        "is_staff",
        "deleted_at",
        "created_at",
    )
    list_filter = ("is_enabled", "is_staff", "is_superuser", "created_at")
    search_fields = ("email", "name", "family_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "last_login", "deleted_at")
    actions = ("send_security_breach_notification",)

    filter_horizontal = ("groups", "user_permissions")

    def get_readonly_fields(self, request, obj=None):
        """Make the email field read-only when editing an existing user.
        Input: request - HttpRequest; obj - User instance or None for new users
        Output: tuple of read-only field names, extended with 'email' when editing
        """
        if obj:
            return self.readonly_fields + ("email",)
        return self.readonly_fields

    @admin.action(
        description="Enviar aviso de brecha de seguridad a todos los usuarios"
    )
    def send_security_breach_notification(self, request, queryset):
        """Send a security breach notification email to all active users and log a SecurityIncident.
        Input: request - HttpRequest from the admin; queryset - selected User queryset (unused, broadcast goes to all)
        Output: None; side-effect: sends emails, creates a SecurityIncident, and shows admin feedback messages
        """
        recipients = list(
            User.objects.filter(is_enabled=True)
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
        if not recipients:
            self.message_user(
                request,
                "No hay usuarios activos con correo para notificar.",
                level=messages.WARNING,
            )
            return

        incident_id = None
        try:
            incident = SecurityIncident.objects.create(
                user=None,
                description=(
                    f"Security breach notification sent to {len(recipients)} active users. "
                    f"Incident logged by {request.user.email}."
                ),
            )
            incident_id = incident.id
        except Exception:
            incident_id = None

        actor = getattr(request.user, "email", "administrador")
        sent = send_security_email(
            subject="Aviso importante de seguridad en Orarioo",
            message="",
            html_message={
                "template": "emails/security/security_breach.html",
                "context": {
                    "incident_summary": (
                        "Se ha detectado una brecha de seguridad que podría haber afectado "
                        "a información gestionada en la plataforma."
                    ),
                    "action_taken": (
                        "Se activó el protocolo interno de respuesta y se inició revisión técnica y organizativa del incidente."
                    ),
                    "issuer": actor,
                },
            },
            recipient_list=recipients,
        )
        if sent:
            msg = f"Notificación enviada a {len(recipients)} usuario(s)."
            if incident_id:
                msg += f" Incidente registrado (ID: {incident_id})."
            self.message_user(request, msg, level=messages.SUCCESS)
        else:
            msg = "No se pudo enviar la notificación de brecha de seguridad."
            if incident_id:
                msg += f" Sin embargo, el incidente fue registrado (ID: {incident_id})."
            self.message_user(request, msg, level=messages.ERROR)

    def save_model(self, request, obj, form, change):
        """Send a lockout email and log a SecurityIncident when a user account is deactivated.
        Input: request - HttpRequest; obj - User instance being saved; form - ModelForm; change - bool True if editing
        Output: None; side-effect: saves the model and, on deactivation, sends a lockout notification email
        """
        was_enabled = None
        if change and obj.pk:
            was_enabled = (
                User.objects.filter(pk=obj.pk)
                .values_list("is_enabled", flat=True)
                .first()
            )

        super().save_model(request, obj, form, change)

        if change and was_enabled is True and obj.is_enabled is False and obj.email:
            reason = (
                "Tu cuenta ha sido desactivada por el equipo administrador "
                "de acuerdo con la política de seguridad de Orarioo."
            )
            try:
                SecurityIncident.objects.create(
                    user=obj,
                    description=f"User account blocked by {request.user.email}. Reason: Account deactivation.",
                )
            except Exception as exc:
                self.message_user(
                    request,
                    f"No se pudo registrar el incidente de seguridad para {obj.email}: {exc}",
                    level=messages.WARNING,
                )

            sent = send_security_email(
                subject="Aviso de seguridad: cuenta bloqueada temporalmente",
                message="",
                html_message={
                    "template": "emails/security/account_lockout.html",
                    "context": {
                        "user_name": obj.get_full_name() or obj.email,
                        "reason": reason,
                    },
                },
                recipient_list=[obj.email],
            )
            if sent:
                self.message_user(
                    request,
                    f"Correo de bloqueo enviado a {obj.email}.",
                    level=messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    (
                        "No se pudo enviar el correo de bloqueo. "
                        "Revisa la configuración SMTP y los logs del servidor."
                    ),
                    level=messages.WARNING,
                )


@admin.register(CollaborationTeam)
class CollaborationTeamAdmin(admin.ModelAdmin):
    """Minimal admin configuration for collaboration team search and member management."""

    list_display = ("name",)
    search_fields = ("name",)
    filter_horizontal = ("members",)


@admin.register(UserDataExportLog)
class UserDataExportLogAdmin(admin.ModelAdmin):
    """Read-only admin view for inspecting GDPR data-export audit log entries."""

    list_display = ("user", "outcome", "created_at")
    list_filter = ("outcome", "created_at")
    search_fields = ("user__email", "notes")
    readonly_fields = (
        "user",
        "created_at",
        "user_agent",
        "outcome",
        "notes",
    )
