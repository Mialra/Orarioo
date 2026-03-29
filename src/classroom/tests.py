from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from auditableEntity.models import AuditActionType, AuditEntry
from classroom.models import Classroom
from common.test_utils import AuthenticatedAdminAPIMixin


class ClassroomApiTests(AuthenticatedAdminAPIMixin, APITestCase):
    def setUp(self):
        self.authenticate_admin(email_prefix="classroom-api")

    def test_create_classroom(self):
        payload = {"name": "Aula 1A"}

        response = self.client.post(reverse("classroom-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Classroom.objects.count(), 1)
        self.assertEqual(Classroom.objects.first().name, "Aula 1A")

    def test_list_and_retrieve_classroom(self):
        classroom = Classroom.objects.create(name="Laboratorio 2")

        list_response = self.client.get(reverse("classroom-list"))
        detail_response = self.client.get(
            reverse("classroom-detail", args=[classroom.id])
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["name"], "Laboratorio 2")

    def test_update_classroom(self):
        classroom = Classroom.objects.create(name="Aula Antiguo Nombre")
        AuditEntry.objects.all().delete()

        payload = {"name": "Aula Nuevo Nombre"}

        response = self.client.put(
            reverse("classroom-detail", args=[classroom.id]), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        classroom.refresh_from_db()
        self.assertEqual(classroom.name, "Aula Nuevo Nombre")
        entry = AuditEntry.objects.filter(entity_type="classroom").latest("id")
        self.assertEqual(entry.action_type, AuditActionType.UPDATE)
        self.assertEqual(entry.entity_name, "Aula Nuevo Nombre")
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(
            entry.changed_fields,
            [
                {
                    "campo": "Nombre",
                    "valor_anterior": "Aula Antiguo Nombre",
                    "valor_nuevo": "Aula Nuevo Nombre",
                }
            ],
        )

    def test_delete_classroom(self):
        classroom = Classroom.objects.create(name="Aula a eliminar")

        response = self.client.delete(reverse("classroom-detail", args=[classroom.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Classroom.objects.filter(id=classroom.id).exists())

    def test_name_is_required(self):
        response = self.client.post(reverse("classroom-list"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_reject_whitespace_only_name(self):
        response = self.client.post(
            reverse("classroom-list"),
            {"name": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_create_non_shared_classroom(self):
        response = self.client.post(
            reverse("classroom-list"),
            {"name": "Aula 3B", "is_shared": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["is_shared"], False)

    def test_reject_case_insensitive_duplicate_name(self):
        Classroom.objects.create(name="Aula Norte")

        response = self.client.post(
            reverse("classroom-list"),
            {"name": "aula norte"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
