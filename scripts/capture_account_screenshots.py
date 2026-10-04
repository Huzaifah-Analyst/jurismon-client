"""Captures high-resolution Playwright screenshots of all 8 customer account states plus 375px mobile view."""

import os
import time
import subprocess
import requests
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "screenshots_p2_1")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

PORT = 8899
BASE_URL = f"http://127.0.0.1:{PORT}"

def wait_for_server(url, timeout=15):
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

def main():
    print("Starting background server on port", PORT)
    proc = subprocess.Popen(
        [os.path.join("venv", "Scripts", "uvicorn.exe"), "api.main:app", "--port", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not wait_for_server(BASE_URL):
            print("Failed to start server")
            return

        print("Server ready. Launching Playwright...")
        with sync_playwright() as p:
            browser = p.chromium.launch()

            # State definitions
            states = [
                ("01_account_signed_out.png", f"{BASE_URL}/account?preview_state=signed_out", 1280, 800),
                ("02_account_loading.png", f"{BASE_URL}/account?preview_state=loading", 1280, 800),
                ("03_account_no_subscription.png", f"{BASE_URL}/account?preview_state=no_subscription", 1280, 800),
                ("04_account_active.png", f"{BASE_URL}/account?preview_state=active", 1280, 800),
                ("05_account_paused.png", f"{BASE_URL}/account?preview_state=paused", 1280, 800),
                ("06_account_cancelled_in_period.png", f"{BASE_URL}/account?preview_state=cancelled_in_period", 1280, 800),
                ("07_account_cancelled_expired.png", f"{BASE_URL}/account?preview_state=cancelled_expired", 1280, 800),
                ("08_account_api_error.png", f"{BASE_URL}/account?preview_state=api_error", 1280, 800),
                ("09_account_mobile_375px.png", f"{BASE_URL}/account?preview_state=active", 375, 812),
            ]

            for filename, url, width, height in states:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(url, wait_until="networkidle")
                time.sleep(0.5)
                out_path = os.path.join(SCREENSHOTS_DIR, filename)
                page.screenshot(path=out_path, full_page=True)
                print(f"Captured: {filename} ({width}x{height}) -> {out_path}")
                page.close()

            browser.close()
            print("All screenshots successfully captured!")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
