"""E2E: horarios guardados en /dashboard/saved/.

Run: pytest tests/e2e/specs/test_saved_schedules.py --base-url http://localhost:8000 -v
"""
import time

import pytest
from playwright.sync_api import Page, expect

_SUFFIX = str(int(time.time()) % 100_000)
RENAMED_SCHEDULE = f"HorarioE2E{_SUFFIX}"


@pytest.fixture()
def saved_page(authenticated_page: Page, base_url: str):
    page = authenticated_page
    page.goto(f"{base_url}/dashboard/saved/")
    page.wait_for_load_state("networkidle")
    # Wait for the cards container to render (AJAX may finish slightly after networkidle)
    page.wait_for_selector("#savedScheduleCards *", timeout=8_000)
    return page


def _cards(page: Page):
    return page.locator(".saved-card")


def test_saved_schedules_tab_loads(saved_page: Page):
    page = saved_page
    expect(page).to_have_url(re.compile(r"saved"), timeout=8_000)
    assert "Error" not in page.title()


def test_saved_schedule_card_is_clickable(saved_page: Page):
    page = saved_page

    if _cards(page).count() == 0:
        pytest.skip("No hay horarios guardados para probar")

    _cards(page).first.click()
    page.wait_for_load_state("networkidle")
    assert "Error" not in page.title()


def test_rename_saved_schedule(saved_page: Page):
    page = saved_page

    if _cards(page).count() == 0:
        pytest.skip("No hay horarios guardados para renombrar")

    _cards(page).first.locator(".saved-card-rename").click()

    modal = page.locator("#renameSavedTimetableModal")
    expect(modal).to_be_visible(timeout=8_000)

    page.fill("#renameSavedTimetableInput", RENAMED_SCHEDULE)
    page.click("#confirmRenameSavedTimetableBtn")

    expect(modal).not_to_be_visible(timeout=10_000)
    expect(page.locator("#scheduleAlert")).to_be_visible(timeout=8_000)


def test_delete_saved_schedule(saved_page: Page):
    page = saved_page

    if _cards(page).count() == 0:
        pytest.skip("No hay horarios guardados para eliminar")

    _cards(page).first.locator(".saved-card-delete").click()

    modal = page.locator("#deleteSavedTimetableModal")
    expect(modal).to_be_visible(timeout=8_000)
    page.click("#confirmDeleteSavedTimetableBtn")

    expect(modal).not_to_be_visible(timeout=10_000)
    expect(page.locator("#scheduleAlert")).to_be_visible(timeout=8_000)
