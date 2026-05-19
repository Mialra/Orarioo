"""E2E: authentication flow.

Run: pytest tests/e2e/specs/ --base-url http://localhost:8000
"""
import os
import re

from playwright.sync_api import Page, expect

EMAIL = os.getenv("E2E_EMAIL", "direccion.academica@test.com")
PASSWORD = os.getenv("E2E_PASSWORD", "direccion123")


def test_successful_login_redirects_to_dashboard(page: Page, base_url: str):
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', EMAIL)
    page.fill('[name="password"]', PASSWORD)
    page.click('[type="submit"]')
    expect(page).to_have_url(re.compile(r"dashboard"), timeout=10_000)


def test_invalid_credentials_shows_error(page: Page, base_url: str):
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', "wrong@test.com")
    page.fill('[name="password"]', "wrongpassword")
    page.click('[type="submit"]')
    expect(page.locator(".auth-alert")).to_be_visible(timeout=8_000)
