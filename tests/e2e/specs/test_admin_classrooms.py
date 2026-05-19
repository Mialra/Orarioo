"""E2E: CRUD de aulas en /dashboard/administration/classrooms/.

Run: pytest tests/e2e/specs/test_admin_classrooms.py --base-url http://localhost:8000 -v
"""
import os
import re
import time

import pytest
from playwright.sync_api import Page, expect

EMAIL = os.getenv("E2E_EMAIL", "direccion.academica@test.com")
PASSWORD = os.getenv("E2E_PASSWORD", "direccion123")

# Unique suffix per run to avoid duplicate-name constraint violations
_SUFFIX = str(int(time.time()) % 100_000)
CLASSROOM_NAME = f"AulaE2E{_SUFFIX}"


@pytest.fixture()
def authenticated_page(page: Page, base_url: str):
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', EMAIL)
    page.fill('[name="password"]', PASSWORD)
    page.click('[type="submit"]')
    expect(page).to_have_url(re.compile(r"dashboard"), timeout=10_000)
    return page


@pytest.fixture()
def classrooms_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/dashboard/administration/classrooms/")
    page.wait_for_load_state("networkidle")
    return page


def test_classroom_list_loads(classrooms_page: Page):
    page = classrooms_page
    expect(page).to_have_url(re.compile(r"classrooms"), timeout=8_000)
    assert "Error" not in page.title()


def test_create_classroom(classrooms_page: Page):
    page = classrooms_page

    page.click("#admin-add-classroom-btn")
    modal = page.locator("#admin-classroom-modal")
    expect(modal).to_be_visible(timeout=8_000)

    page.fill("#admin-classroom-name", CLASSROOM_NAME)

    page.click("#admin-classroom-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-classrooms-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_edit_classroom(classrooms_page: Page):
    page = classrooms_page

    cards = page.locator(".admin-classroom-card")
    if cards.count() == 0:
        pytest.skip("No hay aulas en la lista visible para editar")

    cards.first.locator(".admin-classroom-edit-btn").click()

    modal = page.locator("#admin-classroom-modal")
    expect(modal).to_be_visible(timeout=8_000)

    name_input = page.locator("#admin-classroom-name")
    name_input.fill(f"AulaE2EEdit{_SUFFIX}")

    page.click("#admin-classroom-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-classrooms-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_delete_classroom(classrooms_page: Page):
    page = classrooms_page

    cards = page.locator(".admin-classroom-card")
    if cards.count() == 0:
        pytest.skip("No hay aulas en la lista visible para eliminar")

    cards.first.locator(".admin-classroom-delete-btn").click()

    delete_modal = page.locator("#admin-classroom-delete-modal")
    expect(delete_modal).to_be_visible(timeout=8_000)
    page.click("#admin-classroom-delete-confirm-btn")

    expect(delete_modal).not_to_be_visible(timeout=10_000)
    alert = page.locator("#admin-classrooms-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))
