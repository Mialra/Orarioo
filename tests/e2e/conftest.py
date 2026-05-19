import os
import re

import pytest

EMAIL = os.getenv("E2E_EMAIL", "direccion.academica@test.com")
PASSWORD = os.getenv("E2E_PASSWORD", "direccion123")


@pytest.fixture(scope="session")
def base_url():
    return os.getenv("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "ignore_https_errors": True}


@pytest.fixture(scope="session")
def auth_storage_state(browser, base_url):
    """Login once per session and capture cookies/storage as a snapshot."""
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', EMAIL)
    page.fill('[name="password"]', PASSWORD)
    page.click('[type="submit"]')
    page.wait_for_url(re.compile(r"dashboard"), timeout=15_000)
    state = context.storage_state()
    context.close()
    return state


@pytest.fixture()
def authenticated_page(browser, auth_storage_state, base_url):
    """Isolated per-test context pre-loaded with auth state, starting at /dashboard/."""
    context = browser.new_context(ignore_https_errors=True, storage_state=auth_storage_state)
    page = context.new_page()
    page.goto(f"{base_url}/dashboard/")
    page.wait_for_load_state("networkidle")
    yield page
    context.close()
