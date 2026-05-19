"""E2E: registro de cambios en /dashboard/audit/.

Run: pytest tests/e2e/specs/test_audit.py --base-url http://localhost:8000 -v
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
def audit_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/dashboard/audit/")
    page.wait_for_load_state("networkidle")
    return page


def test_audit_log_loads(audit_page: Page):
    page = audit_page
    expect(page).to_have_url(re.compile(r"audit"), timeout=8_000)
    assert "Error" not in page.title()
    expect(page.locator("#audit-table-body")).to_be_visible(timeout=8_000)


def test_audit_filter_by_entity(audit_page: Page):
    page = audit_page

    entity_select = page.locator("#audit-filter-entity")
    expect(entity_select).to_be_visible(timeout=8_000)

    options = entity_select.locator("option")
    if options.count() < 2:
        pytest.skip("No hay opciones de entidad disponibles para filtrar")

    second_value = options.nth(1).get_attribute("value")
    if second_value:
        page.select_option("#audit-filter-entity", second_value)
        page.wait_for_load_state("networkidle")
        expect(page.locator("#audit-table-body")).to_be_visible(timeout=8_000)


def test_audit_filter_by_date_preset(audit_page: Page):
    page = audit_page

    presets = page.locator("[data-audit-range-preset]")
    if presets.count() == 0:
        pytest.skip("No hay presets de fecha disponibles")

    presets.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#audit-table-body")).to_be_visible(timeout=8_000)
