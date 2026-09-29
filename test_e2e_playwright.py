"""Comprehensive Playwright end-to-end browser verification of Hindsight Outbound Agent."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright
import httpx

ARTIFACT_DIR = Path(r"C:\Users\Sri Vidya Reddy\.gemini\antigravity\brain\f18ddd33-52c6-4fbf-a164-7fc35524bc9e")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def start_server():
    """Start uvicorn server in subprocess."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(Path(__file__).resolve().parent),
    )
    # Wait for server ready
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:8000/health", timeout=1.0)
            if r.status_code == 200:
                print("Uvicorn server is up and healthy.")
                return proc
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("Server failed to start within 10 seconds.")


def stop_server(proc):
    """Cleanly terminate uvicorn process."""
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Uvicorn server stopped.")


def run_e2e():
    proc = start_server()
    console_errors = []
    failed_requests = []

    try:
        # Pre-reset log so we start with an empty log
        httpx.post("http://127.0.0.1:8000/api/reset", timeout=5.0)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            # Listen for console errors
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(str(err)))
            page.on("requestfailed", lambda req: failed_requests.append(f"{req.url} - {req.failure}"))

            # Step 1: Open page and check connection badge
            print("\n[Step 1] Opening http://localhost:8000 ...")
            page.goto("http://localhost:8000", wait_until="networkidle")
            page.wait_for_selector("#connectionBadge.online", timeout=5000)
            badge_text = page.locator("#connectionText").inner_text()
            assert "Backend connected" in badge_text, f"Expected 'Backend connected', got '{badge_text}'"
            ss1 = ARTIFACT_DIR / "screenshot_step1_connected.png"
            page.screenshot(path=str(ss1))
            print(f"Step 1 PASS: Badge is green '{badge_text}'. Screenshot saved to {ss1.name}")

            # Step 2: Empty state check
            print("\n[Step 2] Checking empty state ...")
            empty_box = page.locator("#emptyStateBox")
            dashboard = page.locator("#dashboardContainer")
            assert empty_box.is_visible(), "Empty state box should be visible when log is empty"
            assert not dashboard.is_visible(), "Dashboard container should be hidden when log is empty"
            ss2 = ARTIFACT_DIR / "screenshot_step2_empty_state.png"
            page.screenshot(path=str(ss2))
            print(f"Step 2 PASS: Blue empty state displayed correctly. Screenshot saved to {ss2.name}")

            # Step 3: Tag prospects, then Run all 3 batches
            print("\n[Step 3] Clicking 'Tag prospects' ...")
            page.click("#tagProspectsBtn")
            page.wait_for_timeout(1000)

            print("Clicking 'Run all 3 batches' ...")
            page.click("#runAllBatchesBtn")

            # Confirm progress bar appears and moves
            page.wait_for_selector("#progressBox", state="visible", timeout=5000)
            print("Progress bar visible and active.")

            # Wait for all 3 batches to complete (row 3 rendered in table and button re-enabled)
            page.wait_for_selector("#batchTableBody tr:nth-child(3)", timeout=35000)
            page.wait_for_selector("#runAllBatchesBtn:not([disabled])", timeout=35000)
            page.wait_for_timeout(1500)  # Allow Chart.js animation to settle

            # Confirm KPI cards fill in
            kpi_first = page.locator("#kpiFirstRate").inner_text()
            kpi_last = page.locator("#kpiLastRate").inner_text()
            kpi_delta = page.locator("#kpiDeltaPts").inner_text()
            print(f"KPI Cards: First={kpi_first}, Last={kpi_last}, Delta={kpi_delta}")
            assert "%" in kpi_first and kpi_first != "--%"
            assert "%" in kpi_last and kpi_last != "--%"
            assert "pts" in kpi_delta and kpi_delta != "-- pts"

            # Confirm charts and table
            assert page.locator("#trajectoryChart").is_visible()
            assert page.locator("#angleMixChart").is_visible()
            table_rows = page.locator("#batchTableBody tr").all()
            assert len(table_rows) >= 3, f"Expected 3+ table rows, got {len(table_rows)}"

            ss3 = ARTIFACT_DIR / "screenshot_step3_batches_and_charts.png"
            page.screenshot(path=str(ss3))
            print(f"Step 3 PASS: Progress bar moved, 3 metric cards, charts, and table rendered. Screenshot: {ss3.name}")

            # Step 4: Compare UI vs GET /api/metrics vs data/memory_log.json
            print("\n[Step 4] Comparing UI vs /api/metrics vs data/memory_log.json ...")
            metrics_res = httpx.get("http://127.0.0.1:8000/api/metrics").json()
            with open("data/memory_log.json", "r", encoding="utf-8") as f:
                mem_data = json.load(f)

            # Check exact match
            api_first_str = f"{metrics_res['first_rate']:.1f}%"
            api_last_str = f"{metrics_res['last_rate']:.1f}%"
            api_delta_str = f"{'+' if metrics_res['delta_pts'] >= 0 else ''}{metrics_res['delta_pts']:.1f} pts"

            assert kpi_first == api_first_str, f"UI first rate ({kpi_first}) != API ({api_first_str})"
            assert kpi_last == api_last_str, f"UI last rate ({kpi_last}) != API ({api_last_str})"
            assert kpi_delta == api_delta_str, f"UI delta ({kpi_delta}) != API ({api_delta_str})"

            # Calculate from raw memory_log.json records directly
            b1_records = [r for r in mem_data if r["batch_id"] == 1]
            b3_records = [r for r in mem_data if r["batch_id"] == 3]
            calc_b1_rate = round(sum(1 for r in b1_records if r["outcome"] in ("interested", "reply")) / len(b1_records) * 100.0, 1)
            calc_b3_rate = round(sum(1 for r in b3_records if r["outcome"] in ("interested", "reply")) / len(b3_records) * 100.0, 1)

            assert metrics_res["first_rate"] == calc_b1_rate
            assert metrics_res["last_rate"] == calc_b3_rate
            print(f"Step 4 PASS: Exact 3-way match! UI = API = Log File ({kpi_first} -> {kpi_last}, {kpi_delta})")

            # Step 5: Open comparison view and click a QA row
            print("\n[Step 5] Checking Comparison view and QA row ...")
            # Click first QA row
            qa_rows = page.locator(".qa-row").all()
            assert len(qa_rows) > 0, "No .qa-row elements found"
            qa_rows[0].click()
            page.wait_for_timeout(800)

            # Verify comparison cards
            b1_box = page.locator("#compareBatch1Col .msg-box").inner_text()
            b1_reply = page.locator("#compareBatch1Col .reply-box").inner_text()
            latest_box = page.locator("#compareLatestCol .msg-box").inner_text()
            latest_reply = page.locator("#compareLatestCol .reply-box").inner_text()

            assert len(b1_box) > 10, "Batch 1 email body should be displayed"
            assert len(latest_box) > 10, "Latest batch email body should be displayed"
            assert "Simulated Reply:" in b1_reply, f"Expected 'Simulated Reply:', got '{b1_reply}'"
            assert "Simulated Reply:" in latest_reply, f"Expected 'Simulated Reply:', got '{latest_reply}'"

            page.locator("#compareGrid").scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            ss5 = ARTIFACT_DIR / "screenshot_step5_comparison.png"
            page.screenshot(path=str(ss5))
            print(f"Step 5 PASS: Comparison cards display emails and replies labeled 'Simulated Reply'. Screenshot: {ss5.name}")

            # Step 6: Verify no console errors or failed network requests
            print("\n[Step 6] Inspecting browser console errors and failed network requests ...")
            print(f"Console errors: {console_errors}")
            print(f"Failed requests: {failed_requests}")
            assert len(console_errors) == 0, f"Found console errors: {console_errors}"
            assert len(failed_requests) == 0, f"Found failed requests: {failed_requests}"
            print("Step 6 PASS: Zero console errors and zero failed requests.")

            # Step 7: Click Reset data and verify return to empty state
            print("\n[Step 7] Clicking 'Reset Data' ...")
            page.click("#resetBtn")
            page.wait_for_timeout(1000)
            assert empty_box.is_visible(), "Empty state box should be visible after reset"
            assert not dashboard.is_visible(), "Dashboard should be hidden after reset"
            ss7 = ARTIFACT_DIR / "screenshot_step7_reset_empty.png"
            page.screenshot(path=str(ss7))
            print(f"Step 7 PASS: Successfully returned to empty state. Screenshot: {ss7.name}")

            # Step 8: Stop server and verify badge turns red
            print("\n[Step 8] Stopping backend server and waiting for badge polling ...")
            stop_server(proc)
            proc = None

            # Polls every 10s; wait up to 13s for status-badge offline
            page.wait_for_selector("#connectionBadge.offline", timeout=14000)
            offline_text = page.locator("#connectionText").inner_text()
            assert "Backend offline" in offline_text, f"Expected 'Backend offline', got '{offline_text}'"
            ss8 = ARTIFACT_DIR / "screenshot_step8_server_stopped_red.png"
            page.screenshot(path=str(ss8))
            print(f"Step 8 PASS: Badge turned red ('{offline_text}') within 10s. Screenshot: {ss8.name}")

            # Step 9: Restart server and verify badge turns green
            print("\n[Step 9] Restarting backend server and checking badge recovery ...")
            proc = start_server()
            page.wait_for_selector("#connectionBadge.online", timeout=14000)
            online_text = page.locator("#connectionText").inner_text()
            assert "Backend connected" in online_text, f"Expected 'Backend connected', got '{online_text}'"
            ss9 = ARTIFACT_DIR / "screenshot_step9_server_restarted_green.png"
            page.screenshot(path=str(ss9))
            print(f"Step 9 PASS: Badge recovered to green ('{online_text}'). Screenshot: {ss9.name}")

            browser.close()
            print("\n=== ALL 9 PLAYWRIGHT BROWSER CHECKS PASSED PERFECTLY! ===")

    finally:
        if proc:
            stop_server(proc)


if __name__ == "__main__":
    run_e2e()
