"""E2E: CRUD de profesores en /dashboard/administration/teachers/.

Run: pytest tests/e2e/specs/test_admin_teachers.py --base-url http://localhost:8000 -v
"""
import re
import time

import pytest
from playwright.sync_api import Page, expect

_SUFFIX = str(int(time.time()) % 100_000)


@pytest.fixture()
def teachers_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/dashboard/administration/teachers/")
    page.wait_for_load_state("networkidle")
    return page


def test_teacher_list_loads(teachers_page: Page):
    page = teachers_page
    expect(page).to_have_url(re.compile(r"teachers"), timeout=8_000)
    assert "Error" not in page.title()


def test_create_teacher(teachers_page: Page):
    page = teachers_page

    page.click("#admin-add-teacher-btn")
    modal = page.locator("#admin-teacher-modal")
    expect(modal).to_be_visible(timeout=8_000)

    page.fill("#admin-teacher-name", f"ProfesorE2E{_SUFFIX}")
    page.fill("#admin-teacher-max-weekly-hours", "20")

    page.click("#admin-teacher-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-teachers-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_edit_teacher(teachers_page: Page):
    page = teachers_page

    cards = page.locator(".admin-teacher-card")
    if cards.count() == 0:
        pytest.skip("No hay profesores en la lista visible para editar")

    cards.first.locator(".admin-teacher-edit-btn").click()

    modal = page.locator("#admin-teacher-modal")
    expect(modal).to_be_visible(timeout=8_000)

    name_input = page.locator("#admin-teacher-name")
    name_input.fill(f"ProfesorE2EEdit{_SUFFIX}")

    page.click("#admin-teacher-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-teachers-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_delete_teacher(teachers_page: Page):
    page = teachers_page

    cards = page.locator(".admin-teacher-card")
    if cards.count() == 0:
        pytest.skip("No hay profesores en la lista visible para eliminar")

    cards.first.locator(".admin-teacher-delete-btn").click()

    delete_modal = page.locator("#admin-teacher-delete-modal")
    expect(delete_modal).to_be_visible(timeout=8_000)
    page.click("#admin-teacher-delete-confirm-btn")

    expect(delete_modal).not_to_be_visible(timeout=10_000)
    alert = page.locator("#admin-teachers-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))
