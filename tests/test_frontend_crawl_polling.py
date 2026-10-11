"""Browser regression checks against the real API and isolated SQLite state."""

import socket
import threading
import time
import tempfile
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright, expect

import api.main as main
import api.auth as auth
from db.repository import Repository


@pytest.fixture
def local_browser(monkeypatch, request):
    temporary = tempfile.TemporaryDirectory(prefix="jurismon_browser_")
    repository = Repository(db_path=str(Path(temporary.name) / "browser.db"))
    repository.supabase = None
    monkeypatch.setattr(main, "repo", repository)
    monkeypatch.setattr(auth, "ADMIN_PASSWORD_HASH", auth.get_password_hash("local-browser-password"))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "Local API server did not start"
    try:
        with sync_playwright() as playwright:
            browser = getattr(playwright, getattr(request, "param", "chromium")).launch(timeout=20000)
            page = browser.new_page()
            base = f"http://127.0.0.1:{listener.getsockname()[1]}"
            page.route("**/*", lambda route: route.continue_()
                       if route.request.url.startswith(base + "/") else route.abort())
            yield page, base, repository
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        temporary.cleanup()


@pytest.fixture
def admin_browser(local_browser):
    page, base, _ = local_browser
    response = page.request.post(base + "/api/admin/login", data={
        "email": auth.ADMIN_EMAIL, "password": "local-browser-password",
    })
    assert response.ok
    token = response.json()["access_token"]
    page.add_init_script("localStorage.setItem('jurismon_admin_token', " + repr(token) + ")")
    return local_browser


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "partial_failure"])
def test_running_crawl_updates_then_stops_polling(admin_browser, terminal_status):
    page, base, repository = admin_browser
    run_id = repository.start_crawl_run()
    requests = []
    page.on("request", lambda request: requests.append(request.url)
            if request.url.endswith("/api/admin/crawl/status") else None)
    page.goto(base + "/admin")
    status = page.locator("#crawl-status-line")
    expect(status).to_contain_text("Crawl in progress")
    repository.finish_crawl_run(run_id, terminal_status, total_sources=2,
                               sources_succeeded=1, sources_failed=1)
    expect(status).to_contain_text(terminal_status, timeout=10000)
    expect(page.locator("#btn-run-crawl")).to_be_enabled()
    count = len(requests)
    assert count >= 2
    page.wait_for_timeout(3500)
    assert len(requests) == count


def test_logout_stops_running_crawl_polling(admin_browser):
    page, base, repository = admin_browser
    repository.start_crawl_run()
    requests = []
    page.on("request", lambda request: requests.append(request.url)
            if request.url.endswith("/api/admin/crawl/status") else None)
    page.goto(base + "/admin")
    expect(page.locator("#crawl-status-line")).to_contain_text("Crawl in progress")
    page.locator("#btn-logout").click()
    count = len(requests)
    page.wait_for_timeout(3500)
    assert len(requests) == count
    expect(page.locator("#auth-gate")).to_be_visible()
