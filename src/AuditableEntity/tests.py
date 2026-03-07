from django.test import SimpleTestCase

from auditableEntity.models import AuditableEntity
from namedEntity.models import NamedEntity


class AuditableEntityTests(SimpleTestCase):
    def test_auditable_entity_is_abstract(self):
        self.assertTrue(AuditableEntity._meta.abstract)

    def test_auditable_entity_inherits_named_entity(self):
        self.assertTrue(issubclass(AuditableEntity, NamedEntity))

    def test_auditable_entity_has_audit_fields(self):
        field_names = {field.name for field in AuditableEntity._meta.get_fields()}

        self.assertIn("created_at", field_names)
        self.assertIn("updated_at", field_names)
        self.assertIn("created_by", field_names)
        self.assertIn("updated_by", field_names)
