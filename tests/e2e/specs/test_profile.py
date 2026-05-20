"""E2E: perfil de usuario en /profile/."""
import os
import re
import time

import pytest
from playwright.sync_api import Page, expect

_SUFFIX = str(int(time.time()) % 100_000)
_EMAIL = os.getenv("E2E_EMAIL", "direccion.academica@test.com")
_PASSWORD = os.getenv("E2E_PASSWORD", "direccion123")


def _relogin_and_go_to_profile(page, base_url: str) -> bool:
    """
    Log in fresh and navigate to /profile/. Returns True if the profile page
    loaded successfully (i.e. we are NOT on /sign-in/ after networkidle).
    """
    page.goto(f"{base_url}/sign-in/")
    page.wait_for_load_state("networkidle")
    page.fill('[name="email"]', _EMAIL)
    page.fill('[name="password"]', _PASSWORD)
    page.click('[type="submit"]')
    try:
        page.wait_for_url(re.compile(r"dashboard"), timeout=10_000)
    except Exception:
        return False
    page.wait_for_load_state("networkidle")
    if "/sign-in/" in page.url:
        # dashboard.js also called clearAuthSession — server still struggling
        return False
    page.goto(f"{base_url}/profile/")
    page.wait_for_load_state("networkidle")
    return "/sign-in/" not in page.url


@pytest.fixture()
def profile_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/profile/")
    page.wait_for_load_state("networkidle")
    # Retry loop: the server can reject /api/users/me/ for ~20 s after heavy
    # admin test load. Each attempt takes ~8-10 s, so 4 tries covers ~40 s.
    for _ in range(4):
        if "/sign-in/" not in page.url:
            break
        if _relogin_and_go_to_profile(page, base_url):
            break
    expect(page.locator("#profile-email")).to_be_attached(timeout=10_000)
    return page


def test_profile_page_loads(profile_page: Page):
    page = profile_page
    expect(page).to_have_url(re.compile(r"profile"), timeout=8_000)
    assert "Error" not in page.title()


def test_profile_shows_correct_email(profile_page: Page):
    page = profile_page
    email_el = page.locator("#profile-display-email")
    expect(email_el).to_be_visible(timeout=8_000)
    assert "@" in (email_el.text_content() or "")


def test_profile_shows_current_team(profile_page: Page):
    page = profile_page
    team_el = page.locator("#dashboard-current-team-name")
    expect(team_el).to_be_attached(timeout=8_000)


def test_update_profile_name(profile_page: Page):
    page = profile_page
    page.locator("#profile-personal-edit-trigger").click()
    name_input = page.locator("#profile-given-name")
    expect(name_input).to_be_enabled(timeout=8_000)
    name_input.fill(f"NombreE2E{_SUFFIX}")
    page.locator("#profile-save-btn").click()
    alert = page.locator("#profile-personal-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_change_password_wrong_current(profile_page: Page):
    page = profile_page
    page.locator("#profile-password-edit-trigger").click()
    expect(page.locator("#profile-current-password")).to_be_enabled(timeout=8_000)
    page.fill("#profile-current-password", "wrongpassword123")
    page.fill("#profile-new-password", "newpassword456")
    page.fill("#profile-confirm-password", "newpassword456")
    page.locator("#profile-password-submit").click()
    # Wrong current password triggers a field-level inline error, not the banner alert
    error_el = page.locator("#profile-current-password-error")
    expect(error_el).to_be_visible(timeout=8_000)


def test_delete_account_shows_confirmation_then_cancel(profile_page: Page):
    page = profile_page
    page.locator("#profile-delete-account-trigger").click()
    modal = page.locator("#profileDeleteAccountModal")
    expect(modal).to_be_visible(timeout=8_000)
    modal.locator("[data-bs-dismiss='modal']").first.click()
    expect(modal).not_to_be_visible(timeout=8_000)
