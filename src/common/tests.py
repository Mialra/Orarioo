from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.exceptions import ValidationError

from common.errors.exceptions import ValidationAppError
from common.errors import api_exception_handler
from common.notifications import send_security_email


class ApiExceptionHandlerTests(SimpleTestCase):
    def test_returns_consistent_shape_for_validation_error(self):
        exc = ValidationError({"name": ["name cannot be empty or whitespace only."]})

        response = api_exception_handler(exc, context={})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertIn("errors", response.data)
        self.assertIn("_error", response.data)
        self.assertIn("_meta", response.data)
        self.assertEqual(response.data["_meta"]["success"], False)
        self.assertEqual(
            response.data["name"], ["name cannot be empty or whitespace only."]
        )
        self.assertEqual(
            response.data["errors"]["name"][0]["message"],
            "name cannot be empty or whitespace only.",
        )

    def test_hides_internal_exception_message(self):
        exc = RuntimeError("Database password leaked: super-secret")

        response = api_exception_handler(exc, context={})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["detail"], "An internal server error occurred.")
        self.assertEqual(response.data["_error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("super-secret", str(response.data))

    def test_serializes_app_error_with_structured_field_payload(self):
        exc = ValidationAppError(
            "REQUIRED_FIELD",
            "name is required.",
            field_name="name",
            context={"field": "name"},
        )

        response = api_exception_handler(exc, context={})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["name"], ["name is required."])
        self.assertEqual(response.data["_error"]["code"], "REQUIRED_FIELD")
        self.assertEqual(response.data["errors"]["name"][0]["context"]["field"], "name")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class SecurityNotificationEmailTests(SimpleTestCase):
    def test_send_security_email_with_plain_text(self):
        sent = send_security_email(
            subject="Aviso de seguridad",
            message="Se detecto actividad inusual y se protegió tu cuenta.",
            recipient_list=["user@example.com"],
        )

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Aviso de seguridad")
        self.assertIn("actividad inusual", mail.outbox[0].body)

    def test_send_security_email_renders_html_template_and_builds_text_fallback(self):
        sent = send_security_email(
            subject="Aviso de seguridad",
            message="",
            html_message={
                "template": "emails/security/account_lockout.html",
                "context": {
                    "user_name": "Ana Perez",
                    "reason": "Se detectaron intentos reiterados de acceso fallido.",
                },
            },
            recipient_list=["ana@example.com"],
        )

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Ana Perez", mail.outbox[0].body)
        self.assertIn("privacy.orarioo@gmail.com", mail.outbox[0].body)
        self.assertNotIn("<html", mail.outbox[0].body.lower())
        self.assertIn("Ana Perez", mail.outbox[0].alternatives[0][0])

    def test_send_security_email_logs_and_returns_false_on_error(self):
        with patch(
            "common.notifications.send_mail", side_effect=RuntimeError("smtp down")
        ):
            with self.assertLogs("common.notifications", level="ERROR"):
                sent = send_security_email(
                    subject="Aviso de seguridad",
                    message="Test",
                    recipient_list=["user@example.com"],
                )

        self.assertFalse(sent)
