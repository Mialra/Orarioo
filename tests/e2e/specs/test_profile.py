"""E2E: perfil de usuario en /profile/.

Run: pytest tests/e2e/specs/test_profile.py --base-url http://localhost:8000 -v
"""
import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture()
def profile_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/profile/")
    # Wait for a profile-specific element — this fails fast if app-shell redirected to sign-in.
    expect(page.locator("#profile-email")).to_be_attached(timeout=10_000)
    return page


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
