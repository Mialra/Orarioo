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


def _do_login(page, base_url):
    """Perform a full login and wait until the dashboard is stable."""
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', EMAIL)
    page.fill('[name="password"]', PASSWORD)
    page.click('[type="submit"]')
    page.wait_for_url(re.compile(r"dashboard"), timeout=15_000)
    page.wait_for_load_state("networkidle")


@pytest.fixture(scope="session")
def authenticated_context(browser, base_url):
    """Login once per session. All tests share this context's localStorage (tokens)."""
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    _do_login(page, base_url)
    page.close()
    yield context
    context.close()


@pytest.fixture()
def authenticated_page(authenticated_context, base_url):
    """Per-test page within the shared authenticated context."""
    page = authenticated_context.new_page()
    page.goto(f"{base_url}/dashboard/")
    page.wait_for_load_state("networkidle")
    if "/sign-in/" in page.url:
        _do_login(page, base_url)
    yield page
    page.close()
