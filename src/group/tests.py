from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from group.models import EducationalStage, Group
from user.models import RoleChoices, User


class GroupApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="group-api@test.com",
            password="StrongPassword123!",
            given_name="Api",
            family_name="Tester",
            role=RoleChoices.ADMINISTRATOR,
        )
        self.client.force_authenticate(self.user)

    def test_create_group(self):
        payload = {"name": "1A", "stage": EducationalStage.PRIMARY}

        response = self.client.post(reverse("group-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Group.objects.count(), 1)
        self.assertEqual(Group.objects.first().stage, EducationalStage.PRIMARY)

    def test_list_and_retrieve_group(self):
        group = Group.objects.create(name="2B", stage=EducationalStage.SECONDARY)

        list_response = self.client.get(reverse("group-list"))
        detail_response = self.client.get(reverse("group-detail", args=[group.id]))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["name"], "2B")
        self.assertEqual(detail_response.data["stage"], EducationalStage.SECONDARY)

    def test_update_group(self):
        group = Group.objects.create(name="Infantil", stage=EducationalStage.PRESCHOOL)

        payload = {"name": "Infantil 5", "stage": EducationalStage.PRIMARY}

        response = self.client.patch(
            reverse("group-detail", args=[group.id]), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group.refresh_from_db()
        self.assertEqual(group.name, "Infantil 5")
        self.assertEqual(group.stage, EducationalStage.PRIMARY)

    def test_delete_group(self):
        group = Group.objects.create(name="3C", stage=EducationalStage.PRIMARY)

        response = self.client.delete(reverse("group-detail", args=[group.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Group.objects.filter(id=group.id).exists())

    def test_reject_invalid_stage(self):
        payload = {"name": "X", "stage": "invalid-stage"}

        response = self.client.post(reverse("group-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stage", response.data)
