from django.test import TestCase
from django.urls import reverse


class MainSmokeTests(TestCase):
    def test_placeholder(self):
        self.assertTrue(True)

    def test_dashboard_saved_detail_route_sets_saved_section(self):
        response = self.client.get(
            reverse(
                "dashboard-saved-detail",
                kwargs={"timetable_name": "Horario Demo"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_section"], "saved")
        self.assertEqual(
            response.context["dashboard_saved_timetable_name"],
            "Horario Demo",
        )

    def test_dashboard_saved_route_has_empty_selected_timetable_name(self):
        response = self.client.get(reverse("dashboard-saved"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_section"], "saved")
        self.assertEqual(response.context["dashboard_saved_timetable_name"], "")

    def test_privacy_policy_route_is_public(self):
        response = self.client.get(reverse("privacy-policy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Política de Privacidad")

    def test_terms_conditions_route_is_public(self):
        response = self.client.get(reverse("terms-and-conditions"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Términos y Condiciones de Uso de la plataforma Orarioo"
        )

    def test_security_protocol_route_is_public(self):
        response = self.client.get(reverse("security-protocol"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Protocolo de actuación ante brechas de seguridad")

    def test_footer_is_rendered_on_dashboard_page(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "orarioo-footer")
        self.assertContains(response, "Política de Privacidad")
        self.assertContains(response, "Protocolo de Seguridad")
        self.assertContains(response, "Términos y Condiciones")

    def test_dashboard_includes_profile_link(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("profile"))
        self.assertContains(response, "Mi perfil")
