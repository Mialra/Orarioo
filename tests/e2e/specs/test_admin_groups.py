"""E2E: CRUD de grupos en /dashboard/administration/groups/.

Run: pytest tests/e2e/specs/test_admin_groups.py --base-url http://localhost:8000 -v
"""
import os
import re
import time

import pytest
from playwright.sync_api import Page, expect

EMAIL = os.getenv("E2E_EMAIL", "direccion.academica@test.com")
PASSWORD = os.getenv("E2E_PASSWORD", "direccion123")

_SUFFIX = str(int(time.time()) % 100_000)


@pytest.fixture()
def authenticated_page(page: Page, base_url: str):
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', EMAIL)
    page.fill('[name="password"]', PASSWORD)
    page.click('[type="submit"]')
    expect(page).to_have_url(re.compile(r"dashboard"), timeout=10_000)
    return page


@pytest.fixture()
def groups_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/dashboard/administration/groups/")
    page.wait_for_load_state("networkidle")
    return page


def _select_custom_option(page: Page, select_id: str, option_index: int = 0):
    """Clicks the orarioo-custom-select trigger and selects the option at the given index."""
    wrapper = page.locator(f".orarioo-select-dropdown:has(#{select_id})")
    wrapper.locator(".orarioo-select-trigger").click()
    wrapper.locator(".orarioo-select-option").nth(option_index).click()


def test_group_list_loads(groups_page: Page):
    page = groups_page
    expect(page).to_have_url(re.compile(r"groups"), timeout=8_000)
    assert "Error" not in page.title()


def test_create_group(groups_page: Page):
    page = groups_page

    page.click("#admin-add-group-btn")
    modal = page.locator("#admin-group-modal")
    expect(modal).to_be_visible(timeout=8_000)

    page.fill("#admin-group-name", f"GrupoE2E{_SUFFIX}")
    # Stage select uses orarioo-custom-select; index 0 = first real stage (no placeholder)
    _select_custom_option(page, "admin-group-stage", 0)

    page.click("#admin-group-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-groups-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_edit_group(groups_page: Page):
    page = groups_page

    cards = page.locator(".admin-group-card")
    if cards.count() == 0:
        pytest.skip("No hay grupos en la lista visible para editar")

    cards.first.locator(".admin-group-edit-btn").click()

    modal = page.locator("#admin-group-modal")
    expect(modal).to_be_visible(timeout=8_000)

    name_input = page.locator("#admin-group-name")
    name_input.fill(f"GrupoE2EEdit{_SUFFIX}")

    page.click("#admin-group-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-groups-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_delete_group(groups_page: Page):
    page = groups_page

    cards = page.locator(".admin-group-card")
    if cards.count() == 0:
        pytest.skip("No hay grupos en la lista visible para eliminar")

    cards.first.locator(".admin-group-delete-btn").click()

    delete_modal = page.locator("#admin-group-delete-modal")
    expect(delete_modal).to_be_visible(timeout=8_000)
    page.click("#admin-group-delete-confirm-btn")

    expect(delete_modal).not_to_be_visible(timeout=10_000)
    alert = page.locator("#admin-groups-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))
