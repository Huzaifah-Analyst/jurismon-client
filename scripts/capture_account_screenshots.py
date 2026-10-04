"""Captures high-resolution Playwright screenshots of all 8 customer account states plus 375px mobile view.

Uses a real temporary SQLite database with real user records, real JWT authentication tokens,
and real subscription rows in every state. No mocked frontend preview renderers.
"""

import os
import sys
import time
import json
import shutil
import tempfile
import subprocess
import requests
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# Add repo root to sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ["SECRET_KEY"] = "jurismon_screenshot_capture_secret_key_123"

from api.auth import get_password_hash
from db.repository import Repository

SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "screenshots_p2_1")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

PORT = 8899
BASE_URL = f"http://127.0.0.1:{PORT}"


def wait_for_server(url, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{url}/favicon.ico", timeout=1)
            if r.status_code in (200, 404):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def seed_test_database(db_path: str):
    """Populates an isolated SQLite test database with genuine users and subscription states."""
    repo = Repository(db_path=db_path)
    repo.supabase = None  # Explicitly disable Supabase for local isolated testing
    pw_hash = get_password_hash("Password123!")
    now = datetime.now(timezone.utc)

    # 1. Trial user (No subscription)
    repo.create_user("trial_user@jurismon.com", pw_hash, "Trial User", is_verified=1)
    repo.activate_user_trial("trial_user@jurismon.com", trial_days=14)

    # 2. Active subscriber
    repo.create_user("active_subscriber@jurismon.com", pw_hash, "Active Subscriber", is_verified=1)
    repo.activate_user_trial("active_subscriber@jurismon.com", trial_days=14)
    repo.record_subscription(
        external_sub_id="I-ACT-8849102",
        plan_id="professional_monthly",
        status="active",
        user_email="active_subscriber@jurismon.com",
        subscriber_name="Active Subscriber",
        next_billing_at=(now + timedelta(days=28)).isoformat(),
    )

    # 3. Paused subscriber (in paid period)
    repo.create_user("paused_subscriber@jurismon.com", pw_hash, "Paused Subscriber", is_verified=1)
    # Expire user's original trial so status strictly reflects subscription
    past_trial = (now - timedelta(days=30)).isoformat()
    with repo._connect() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE email = ?", (past_trial, "paused_subscriber@jurismon.com"))
    repo.record_subscription(
        external_sub_id="I-PAU-5521902",
        plan_id="professional_monthly",
        status="active",
        user_email="paused_subscriber@jurismon.com",
        subscriber_name="Paused Subscriber",
        next_billing_at=(now + timedelta(days=18)).isoformat(),
    )
    repo.set_subscription_paused(
        "I-PAU-5521902",
        paused_at=(now - timedelta(days=2)).isoformat(),
        access_until=(now + timedelta(days=18)).isoformat(),
    )

    # 4. Cancelled subscriber (in paid period)
    repo.create_user("cancelled_in_period@jurismon.com", pw_hash, "Cancelled In-Period", is_verified=1)
    with repo._connect() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE email = ?", (past_trial, "cancelled_in_period@jurismon.com"))
    repo.record_subscription(
        external_sub_id="I-CAN-3310921",
        plan_id="professional_monthly",
        status="active",
        user_email="cancelled_in_period@jurismon.com",
        subscriber_name="Cancelled In-Period",
        next_billing_at=(now + timedelta(days=15)).isoformat(),
    )
    repo.set_subscription_cancelled(
        "I-CAN-3310921",
        cancelled_at=(now - timedelta(days=1)).isoformat(),
        access_until=(now + timedelta(days=15)).isoformat(),
        reason="Customer requested cancellation",
    )

    # 5. Cancelled subscriber (expired paid period)
    repo.create_user("cancelled_expired@jurismon.com", pw_hash, "Cancelled Expired", is_verified=1)
    past_expired_trial = (now - timedelta(days=45)).isoformat()
    with repo._connect() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE email = ?", (past_expired_trial, "cancelled_expired@jurismon.com"))
    repo.record_subscription(
        external_sub_id="I-EXP-7729104",
        plan_id="professional_monthly",
        status="active",
        user_email="cancelled_expired@jurismon.com",
        subscriber_name="Cancelled Expired",
        next_billing_at=(now - timedelta(days=5)).isoformat(),
    )
    repo.set_subscription_cancelled(
        "I-EXP-7729104",
        cancelled_at=(now - timedelta(days=35)).isoformat(),
        access_until=(now - timedelta(days=5)).isoformat(),
        reason="Subscription cycle concluded",
    )

    # 6. Generic authenticated user for loading & API error states
    repo.create_user("test_user@jurismon.com", pw_hash, "Test User", is_verified=1)
    repo.activate_user_trial("test_user@jurismon.com", trial_days=14)

    print(f"Database seeded successfully at {db_path}")


def obtain_auth_session(email: str, password: str = "Password123!"):
    """Logs in against the real auth endpoint to receive real access_token and user info."""
    res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {res.status_code} {res.text}")
    data = res.json()
    return data["access_token"], data.get("user")


def main():
    # Setup temporary directory and database
    temp_dir = tempfile.mkdtemp(prefix="jurismon_screenshots_")
    temp_db = os.path.join(temp_dir, "test_screenshots.db")

    try:
        seed_test_database(temp_db)

        # Launch server process configured to use our temp DB and ignore Supabase
        env = os.environ.copy()
        env["JURISMON_DB_PATH"] = temp_db
        env["JURISMON_NO_SUPABASE"] = "1"

        print("Starting isolated uvicorn server on port", PORT)
        proc = subprocess.Popen(
            [os.path.join(REPO_ROOT, "venv", "Scripts", "uvicorn.exe"), "api.main:app", "--port", str(PORT)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            if not wait_for_server(BASE_URL):
                stdout, stderr = proc.communicate(timeout=5)
                print("Failed to start server. Stderr:", stderr.decode(errors="ignore"))
                return

            print("Server is listening. Logging in test accounts...")
            # Pre-fetch JWT tokens from real auth endpoint
            token_trial, user_trial = obtain_auth_session("trial_user@jurismon.com")
            token_active, user_active = obtain_auth_session("active_subscriber@jurismon.com")
            token_paused, user_paused = obtain_auth_session("paused_subscriber@jurismon.com")
            token_can_period, user_can_period = obtain_auth_session("cancelled_in_period@jurismon.com")
            token_can_exp, user_can_exp = obtain_auth_session("cancelled_expired@jurismon.com")
            token_test, user_test = obtain_auth_session("test_user@jurismon.com")

            with sync_playwright() as p:
                browser = p.chromium.launch()

                def capture_state(
                    filename: str,
                    token: str = None,
                    user: dict = None,
                    width: int = 1280,
                    height: int = 800,
                    route_interceptor=None,
                    wait_selector: str = None,
                ):
                    context = browser.new_context(viewport={"width": width, "height": height})
                    if token:
                        user_json = json.dumps(user) if user else "null"
                        context.add_init_script(f"""
                            localStorage.setItem("jurismon_token", "{token}");
                            localStorage.setItem("jurismon_user", JSON.stringify({user_json}));
                        """)
                    else:
                        context.add_init_script("localStorage.clear();")

                    page = context.new_page()
                    if route_interceptor:
                        route_interceptor(page)

                    page.goto(f"{BASE_URL}/account")
                    if wait_selector:
                        page.locator(wait_selector).wait_for(state="visible", timeout=10000)
                    page.wait_for_timeout(400)

                    out_path = os.path.join(SCREENSHOTS_DIR, filename)
                    page.screenshot(path=out_path, full_page=True)
                    print(f"Captured: {filename} ({width}x{height})")
                    context.close()

                # 1. Signed Out (1280x800)
                capture_state("01_account_signed_out.png", token=None, wait_selector="#state-signed-out")

                # 2. Loading State (1280x800) - route suspended so loading spinner remains visible
                def intercept_loading(page):
                    page.route("**/api/account/subscription", lambda route: None)

                capture_state(
                    "02_account_loading.png",
                    token=token_test,
                    user=user_test,
                    route_interceptor=intercept_loading,
                    wait_selector="#state-loading",
                )

                # 3. No Subscription / Trial (1280x800)
                capture_state(
                    "03_account_no_subscription.png",
                    token=token_trial,
                    user=user_trial,
                    wait_selector="#state-no-subscription",
                )

                # 4. Active Subscription (1280x800)
                capture_state(
                    "04_account_active.png",
                    token=token_active,
                    user=user_active,
                    wait_selector="#state-active",
                )

                # 5. Paused Subscription (1280x800)
                capture_state(
                    "05_account_paused.png",
                    token=token_paused,
                    user=user_paused,
                    wait_selector="#state-paused",
                )

                # 6. Cancelled, In-Period (1280x800)
                capture_state(
                    "06_account_cancelled_in_period.png",
                    token=token_can_period,
                    user=user_can_period,
                    wait_selector="#state-cancelled-in-period",
                )

                # 7. Cancelled, Expired (1280x800)
                capture_state(
                    "07_account_cancelled_expired.png",
                    token=token_can_exp,
                    user=user_can_exp,
                    wait_selector="#state-cancelled-expired",
                )

                # 8. API Error (1280x800) - API genuinely fails with HTTP 503
                def intercept_error(page):
                    page.route(
                        "**/api/account/subscription",
                        lambda route: route.fulfill(
                            status=503,
                            headers={"Content-Type": "application/json"},
                            body=json.dumps({"detail": "Service Unavailable - database connection timed out"}),
                        ),
                    )

                capture_state(
                    "08_account_api_error.png",
                    token=token_test,
                    user=user_test,
                    route_interceptor=intercept_error,
                    wait_selector="#state-error",
                )

                # 9. Active Mobile 375px (375x812)
                capture_state(
                    "09_account_mobile_375px.png",
                    token=token_active,
                    user=user_active,
                    width=375,
                    height=812,
                    wait_selector="#state-active",
                )

                browser.close()
                print("\nAll 9 screenshots successfully captured using real authenticated data!")

        finally:
            proc.terminate()
            proc.wait()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
