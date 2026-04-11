from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from common.notifications import send_security_email
from securityIncident.models import SecurityIncident
from user.models import CollaborationTeam, User, UserDataExportLog


@admin.register(User)
class UserAdmin(UserAdmin):
    """Custom configuration for user management in the admin panel"""

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
        """Makes certain fields read-only"""
        if obj:  # When editing an existing user
            return self.readonly_fields + ("email",)
        return self.readonly_fields

    @admin.action(
        description="Enviar aviso de brecha de seguridad a todos los usuarios"
    )
    def send_security_breach_notification(self, request, queryset):
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
            except Exception:
                pass

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
    list_display = ("name",)
    search_fields = ("name",)
    filter_horizontal = ("members",)


@admin.register(UserDataExportLog)
class UserDataExportLogAdmin(admin.ModelAdmin):
    list_display = ("user", "outcome", "ip_address", "created_at")
    list_filter = ("outcome", "created_at")
    search_fields = ("user__email", "ip_address", "notes")
    readonly_fields = (
        "user",
        "created_at",
        "ip_address",
        "user_agent",
        "outcome",
        "notes",
    )
