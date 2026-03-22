from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError

from common.exceptions import api_exception_handler


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

    def test_hides_internal_exception_message(self):
        exc = RuntimeError("Database password leaked: super-secret")

        response = api_exception_handler(exc, context={})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["detail"], "An internal server error occurred.")
        self.assertNotIn("super-secret", str(response.data))
