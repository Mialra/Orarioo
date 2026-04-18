from django.db.models import SET_NULL
from django.test import SimpleTestCase, TestCase

from securityIncident.models import SecurityIncident
from user.models import User

_LONG_DESCRIPTION = "A" * 10_000


class SecurityIncidentMetaTests(SimpleTestCase):
    """Tests for model-level schema and meta configuration."""

    def test_db_table_name(self):
        self.assertEqual(SecurityIncident._meta.db_table, "security_incident")

    def test_ordering_is_newest_first(self):
        self.assertEqual(SecurityIncident._meta.ordering, ["-created_at"])

    def test_user_field_set_null_on_delete(self):
        user_field = SecurityIncident._meta.get_field("user")
        self.assertIs(user_field.remote_field.on_delete, SET_NULL)


class SecurityIncidentUserLabelTests(SimpleTestCase):
    """Tests for _user_label logic."""

    def test_user_label_without_user_returns_deleted_user(self):
        incident = SecurityIncident(user=None, description="test")
        self.assertEqual(incident._user_label(), "Deleted user")


class SecurityIncidentTests(TestCase):
    """DB tests covering creation, boundaries, ordering, SET_NULL, and str formatting."""

    def _create_user(self, email="test@example.com"):
        return User.objects.create_user(
            email=email,
            given_name="Test",
            family_name="User",
            password="StrongPassword123!",
        )

    def test_create_incident_with_user_persists_all_fields(self):
        user = self._create_user()
        incident = SecurityIncident.objects.create(
            user=user,
            description="Intentos fallidos de acceso.",
        )
        incident.refresh_from_db()

        self.assertEqual(incident.user, user)
        self.assertEqual(incident.description, "Intentos fallidos de acceso.")
        self.assertIsNotNone(incident.created_at)

    def test_create_incident_without_user_persists_correctly(self):
        incident = SecurityIncident.objects.create(
            user=None,
            description="Actividad sospechosa de IP desconocida.",
        )
        incident.refresh_from_db()

        self.assertIsNone(incident.user)
        self.assertIsNotNone(incident.created_at)

    def test_created_at_is_set_automatically(self):
        incident = SecurityIncident.objects.create(description="auto timestamp test")
        self.assertIsNotNone(incident.created_at)

    def test_description_empty_string_is_accepted(self):
        incident = SecurityIncident.objects.create(description="")
        self.assertEqual(incident.description, "")

    def test_description_single_character_is_accepted(self):
        incident = SecurityIncident.objects.create(description="X")
        self.assertEqual(incident.description, "X")

    def test_description_long_text_is_stored_intact(self):
        incident = SecurityIncident.objects.create(description=_LONG_DESCRIPTION)
        incident.refresh_from_db()
        self.assertEqual(len(incident.description), 10_000)

    def test_ordering_returns_newest_incident_first(self):
        first = SecurityIncident.objects.create(description="Primero")
        second = SecurityIncident.objects.create(description="Segundo")
        third = SecurityIncident.objects.create(description="Tercero")

        incidents = list(SecurityIncident.objects.all())

        self.assertEqual(incidents[0], third)
        self.assertEqual(incidents[1], second)
        self.assertEqual(incidents[2], first)

    def test_user_set_null_when_linked_user_is_deleted(self):
        user = self._create_user("victim@example.com")
        incident = SecurityIncident.objects.create(
            user=user,
            description="Cuenta bloqueada por intentos excesivos.",
        )

        user.delete()
        incident.refresh_from_db()

        self.assertIsNone(incident.user)

    def test_user_label_with_active_user_returns_email(self):
        user = self._create_user("active@example.com")
        incident = SecurityIncident.objects.create(user=user, description="test")
        self.assertEqual(incident._user_label(), "User active@example.com")

    def test_str_with_user_contains_id_and_email(self):
        user = self._create_user("shown@example.com")
        incident = SecurityIncident.objects.create(user=user, description="test")
        result = str(incident)

        self.assertIn(f"SecurityIncident {incident.id}", result)
        self.assertIn("User shown@example.com", result)

    def test_str_without_user_contains_id_and_deleted_user_label(self):
        incident = SecurityIncident.objects.create(user=None, description="test")
        result = str(incident)

        self.assertIn(f"SecurityIncident {incident.id}", result)
        self.assertIn("Deleted user", result)
