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
    """Perform a full login and wait until app-shell.js has committed tokens to localStorage."""
    page.goto(f"{base_url}/sign-in/")
    page.fill('[name="email"]', EMAIL)
    page.fill('[name="password"]', PASSWORD)
    page.click('[type="submit"]')
    page.wait_for_url(re.compile(r"dashboard"), timeout=15_000)
    page.wait_for_load_state("networkidle")
    # Wait until app-shell.js has written the access token to localStorage.
    # #logout-button is server-rendered so it cannot be used as a readiness signal.
    page.wait_for_function(
        "() => Boolean(window.localStorage.getItem('orarioo_access_token'))",
        timeout=15_000,
    )


@pytest.fixture(scope="session")
def auth_storage_state(browser, base_url):
    """Login once per session and capture localStorage tokens + cookies as a snapshot."""
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    _do_login(page, base_url)
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
    if "/sign-in/" in page.url:
        _do_login(page, base_url)
    else:
        page.wait_for_function(
            "() => Boolean(window.localStorage.getItem('orarioo_access_token'))",
            timeout=15_000,
        )
    yield page
    context.close()
