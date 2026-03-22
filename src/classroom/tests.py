from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

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

        payload = {"name": "Aula Nuevo Nombre"}

        response = self.client.put(
            reverse("classroom-detail", args=[classroom.id]), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        classroom.refresh_from_db()
        self.assertEqual(classroom.name, "Aula Nuevo Nombre")

    def test_delete_classroom(self):
        classroom = Classroom.objects.create(name="Aula a eliminar")

        response = self.client.delete(reverse("classroom-detail", args=[classroom.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Classroom.objects.filter(id=classroom.id).exists())

    def test_name_is_required(self):
        response = self.client.post(reverse("classroom-list"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
