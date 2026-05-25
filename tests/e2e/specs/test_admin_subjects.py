"""E2E: CRUD de asignaturas en /dashboard/administration/subjects/.

Prerequisito: debe existir al menos un profesor, un grupo y un aula en la BD.
Run: pytest tests/e2e/specs/test_admin_subjects.py --base-url http://localhost:8000 -v
"""
import re
import time

import pytest
from playwright.sync_api import Page, expect

_SUFFIX = str(int(time.time()) % 100_000)


@pytest.fixture()
def subjects_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/dashboard/administration/subjects/")
    page.wait_for_load_state("networkidle")
    return page


def _select_custom_option(page: Page, select_id: str, option_index: int) -> bool:
    """
    Interacts with an orarioo-custom-select widget.
    Returns False if the dropdown has no options at the given index (caller should skip).
    Index 0 is typically a placeholder; real data starts at index 1.
    """
    wrapper = page.locator(f".orarioo-select-dropdown:has(#{select_id})")
    wrapper.locator(".orarioo-select-trigger").click()
    options = wrapper.locator(".orarioo-select-option")
    if options.count() <= option_index:
        return False
    options.nth(option_index).click()
    return True


def test_subject_list_loads(subjects_page: Page):
    page = subjects_page
    expect(page).to_have_url(re.compile(r"subjects"), timeout=8_000)
    assert "Error" not in page.title()


def test_create_subject(subjects_page: Page):
    page = subjects_page

    page.click("#admin-add-subject-btn")
    modal = page.locator("#admin-subject-modal")
    expect(modal).to_be_visible(timeout=8_000)

    # Wait for relation data (teacher/group/classroom) to load via AJAX
    page.wait_for_load_state("networkidle")

    page.fill("#admin-subject-name", f"AsignaturaE2E{_SUFFIX}")
    page.fill("#admin-subject-weekly-hours", "3")

    # Index 0 = placeholder ("Selecciona…"), index 1 = first real item
    teacher_ok = _select_custom_option(page, "admin-subject-teacher", 1)
    group_ok = _select_custom_option(page, "admin-subject-group", 1)
    classroom_ok = _select_custom_option(page, "admin-subject-classroom", 1)

    if not (teacher_ok and group_ok and classroom_ok):
        pytest.skip("No hay suficientes datos (profesor/grupo/aula) para crear asignatura")

    page.click("#admin-subject-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-subjects-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_edit_subject(subjects_page: Page):
    page = subjects_page

    cards = page.locator(".admin-subject-card")
    if cards.count() == 0:
        pytest.skip("No hay asignaturas en la lista visible para editar")

    cards.first.locator(".admin-subject-edit-btn").click()

    modal = page.locator("#admin-subject-modal")
    expect(modal).to_be_visible(timeout=8_000)

    name_input = page.locator("#admin-subject-name")
    name_input.fill(f"AsignaturaE2EEdit{_SUFFIX}")

    page.click("#admin-subject-submit-btn")
    expect(modal).not_to_be_visible(timeout=10_000)

    alert = page.locator("#admin-subjects-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))


def test_delete_subject(subjects_page: Page):
    page = subjects_page

    cards = page.locator(".admin-subject-card")
    if cards.count() == 0:
        pytest.skip("No hay asignaturas en la lista visible para eliminar")

    cards.first.locator(".admin-subject-delete-btn").click()

    delete_modal = page.locator("#admin-subject-delete-modal")
    expect(delete_modal).to_be_visible(timeout=8_000)
    page.click("#admin-subject-delete-confirm-btn")

    expect(delete_modal).not_to_be_visible(timeout=10_000)
    alert = page.locator("#admin-subjects-alert")
    expect(alert).to_be_visible(timeout=8_000)
    expect(alert).to_have_class(re.compile(r"alert-success"))
