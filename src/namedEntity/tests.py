from django.test import SimpleTestCase

from namedEntity.models import NamedEntity


class NamedEntityTests(SimpleTestCase):
    def test_named_entity_is_abstract(self):
        self.assertTrue(NamedEntity._meta.abstract)

    def test_named_entity_has_name_field(self):
        name_field = NamedEntity._meta.get_field("name")

        self.assertEqual(name_field.max_length, 150)
