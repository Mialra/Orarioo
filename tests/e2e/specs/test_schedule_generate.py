"""E2E: schedule generation golden path.

Prerequisites: at least one teacher, group, and subject must exist in the DB.
Run: pytest tests/e2e/specs/ --base-url http://localhost:8000
"""
import re

import pytest
from playwright.sync_api import Page, expect


def test_navigates_to_dashboard_and_triggers_generation(authenticated_page: Page):
    page = authenticated_page
    expect(page).to_have_url(re.compile(r"dashboard"))

    # Espera a que el JavaScript del dashboard termine de cargar
    page.wait_for_load_state("networkidle")

    # Abre el modal de generación
    btn = page.get_by_role("button", name=re.compile(r"generar horario", re.IGNORECASE)).first
    expect(btn).to_be_visible(timeout=8_000)
    btn.click()

    # Confirma dentro del modal (el segundo botón "Generar horario" dentro del dialog)
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=8_000)
    dialog.get_by_role("button", name=re.compile(r"generar horario", re.IGNORECASE)).click()

    # Espera a que el modal se cierre (generación en curso o completada)
    expect(dialog).not_to_be_visible(timeout=90_000)


def test_dashboard_loads_for_authenticated_user(authenticated_page: Page):
    page = authenticated_page
    expect(page).to_have_url(re.compile(r"dashboard"))
    expect(page).not_to_have_title("Error")
