"""E2E: navigation — verifica que las rutas principales cargan correctamente.

Run: pytest tests/e2e/specs/test_navigation.py --base-url http://localhost:8000 -v
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


def test_root_redirects_to_sign_in(page: Page, base_url: str):
    page.goto(f"{base_url}/")
    expect(page).to_have_url(re.compile(r"sign-in"), timeout=8_000)


def test_dashboard_sections_are_reachable(authenticated_page: Page, base_url: str):
    page = authenticated_page
    for path in ["/dashboard/", "/dashboard/saved/", "/dashboard/audit/"]:
        page.goto(f"{base_url}{path}")
        page.wait_for_load_state("networkidle")
        assert "Error" not in page.title(), f"{path} returned an error page"


def test_admin_sections_are_reachable(authenticated_page: Page, base_url: str):
    page = authenticated_page
    sections = [
        "/dashboard/administration/teachers/",
        "/dashboard/administration/groups/",
        "/dashboard/administration/subjects/",
        "/dashboard/administration/classrooms/",
        "/dashboard/administration/schedule-config/",
    ]
    for path in sections:
        page.goto(f"{base_url}{path}")
        page.wait_for_load_state("networkidle")
        assert "Error" not in page.title(), f"{path} returned an error page"


def test_legal_pages_are_reachable(page: Page, base_url: str):
    for path in ["/privacy-policy/", "/terms-and-conditions/", "/security-protocol/"]:
        page.goto(f"{base_url}{path}")
        page.wait_for_load_state("load")
        assert "Error" not in page.title(), f"{path} returned an error page"
