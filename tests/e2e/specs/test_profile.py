"""E2E: perfil de usuario en /profile/.

Run: pytest tests/e2e/specs/test_profile.py --base-url http://localhost:8000 -v
"""
import os
import re

import pytest
from playwright.sync_api import Page, expect

EMAIL = os.getenv("E2E_EMAIL", "direccion.academica@test.com")
PASSWORD = os.getenv("E2E_PASSWORD", "direccion123")


@pytest.fixture()
def authenticated_page(page: Page, base_url: str):
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', EMAIL)
    page.fill('[name="password"]', PASSWORD)
    page.click('[type="submit"]')
    expect(page).to_have_url(re.compile(r"dashboard"), timeout=10_000)
    return page


@pytest.fixture()
def profile_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/profile/")
    page.wait_for_load_state("networkidle")
    return page


def test_profile_page_loads(profile_page: Page):
    page = profile_page
    expect(page).to_have_url(re.compile(r"profile"), timeout=8_000)
    assert "Error" not in page.title()


def test_profile_shows_correct_email(profile_page: Page):
    page = profile_page
    # The email field is always read-only; read its value directly via JS
    email_value = page.locator("#profile-email").evaluate("el => el.value")
    assert email_value, "El campo email no debe estar vacío"
    assert "@" in email_value, f"El valor del email no parece un email válido: {email_value!r}"


def test_profile_shows_current_team(profile_page: Page):
    page = profile_page
    # dashboard-current-team-name lives inside the collapsed dropdown; read it via JS
    # so we don't need to open the menu (avoids Bootstrap animation timing issues)
    team_name = page.evaluate(
        "() => (document.getElementById('dashboard-current-team-name') || {}).textContent?.trim() || ''"
    )
    assert team_name and team_name != "-", (
        f"El nombre del equipo activo no está inicializado: {team_name!r}"
    )


def test_update_profile_name(profile_page: Page):
    page = profile_page

    # Fields are disabled by default; click the edit trigger to enable them
    page.click("#profile-personal-edit-trigger")

    given_name = page.locator("#profile-given-name")
    expect(given_name).to_be_enabled(timeout=5_000)

    original = given_name.input_value()
    given_name.fill("NombreE2E")

    page.click("#profile-save-btn")
    page.wait_for_load_state("networkidle")

    alert = page.locator("#profile-personal-alert")
    expect(alert).to_be_visible(timeout=8_000)

    # Restore original name
    page.click("#profile-personal-edit-trigger")
    expect(given_name).to_be_enabled(timeout=5_000)
    given_name.fill(original)
    page.click("#profile-save-btn")
    page.wait_for_load_state("networkidle")


def test_change_password_wrong_current(profile_page: Page):
    page = profile_page

    # Fields are disabled by default; click the edit trigger to enable them
    page.click("#profile-password-edit-trigger")

    current_pw = page.locator("#profile-current-password")
    expect(current_pw).to_be_enabled(timeout=5_000)

    page.fill("#profile-current-password", "contraseña_incorrecta_xyz")
    page.fill("#profile-new-password", "NuevaContra123!")
    page.fill("#profile-confirm-password", "NuevaContra123!")

    page.click("#profile-password-submit")
    page.wait_for_load_state("networkidle")

    # Either the main alert or a field-level error must appear
    alert_or_error = page.locator(
        "#profile-password-alert, #profile-current-password-error, #profile-new-password-error"
    )
    expect(alert_or_error.first).to_be_visible(timeout=8_000)


def test_delete_account_shows_confirmation_then_cancel(profile_page: Page):
    page = profile_page

    trigger = page.locator("#profile-delete-account-trigger")
    expect(trigger).to_be_visible(timeout=8_000)
    trigger.click()

    modal = page.locator("#profileDeleteAccountModal")
    expect(modal).to_be_visible(timeout=8_000)

    cancel_btn = modal.get_by_role("button", name=re.compile(r"cancelar|cancel", re.IGNORECASE))
    cancel_btn.click()

    expect(modal).not_to_be_visible(timeout=8_000)
    expect(page).to_have_url(re.compile(r"profile"), timeout=5_000)
