"""
Playwright Integration Test: Financial Performance Dashboard

This test actually launches the dashboard and verifies:
1. The Financial Performance page loads correctly
2. The Portfolio Value metric is displayed
3. The value shown matches the database calculation

This is an END-TO-END test that validates the entire stack:
- Database queries
- Dashboard rendering
- Streamlit UI display

NOTE: These are integration tests that require a production PostgreSQL database
with real betting data. They will be skipped when running in test environments.
"""

import os
import sys
from pathlib import Path
import re
import pytest
from playwright.sync_api import sync_playwright

sys.path.append(str(Path(__file__).parent.parent))

from plugins.db_manager import DBManager

# Skip these tests unless running against production database
pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") != "postgres",
    reason="Integration tests require production PostgreSQL database",
)


def test_financial_performance_shows_correct_portfolio_value():
    """
    Integration Test: Verify dashboard displays correct portfolio value

    This test:
    1. Calculates expected portfolio value from database
    2. Launches real dashboard with Playwright
    3. Navigates to Financial Performance page
    4. Verifies displayed value matches calculation
    """
    print("\n" + "=" * 80)
    print("INTEGRATION TEST: Financial Performance Dashboard")
    print("=" * 80)

    # Step 1: Calculate expected portfolio value from database
    db = DBManager()

    # Get cash balance
    cash_df = db.fetch_df(
        """
        SELECT ROUND(balance_dollars::numeric, 2) as cash
        FROM portfolio_value_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
    """
    )

    # Get open positions value
    open_df = db.fetch_df(
        """
        SELECT ROUND(SUM(cost_dollars)::numeric, 2) as open_value
        FROM placed_bets
        WHERE status = 'open'
    """
    )

    if cash_df.empty:
        print("\n❌ No portfolio snapshots - cannot run test")
        return False

    cash = float(cash_df.iloc[0]["cash"])
    open_value = (
        float(open_df.iloc[0]["open_value"])
        if not open_df.empty and open_df.iloc[0]["open_value"]
        else 0.0
    )
    expected_portfolio_value = cash + open_value

    print("\n📊 Expected Values (from database):")
    print(f"   Cash Balance: ${cash:.2f}")
    print(f"   Open Positions: ${open_value:.2f}")
    print(f"   Portfolio Value: ${expected_portfolio_value:.2f}")

    # Step 2: Launch dashboard with Playwright
    print("\n🌐 Launching dashboard...")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to dashboard (assumes running on localhost:8501)
        dashboard_url = "http://localhost:8501"
        print(f"   Opening {dashboard_url}")

        try:
            page.goto(dashboard_url, timeout=30000)

            # Wait for Streamlit to load
            page.wait_for_load_state("networkidle")

            print("   ✅ Dashboard loaded")

            # Step 3: Navigate to Financial Performance
            # Look for sidebar navigation or main page
            print("\n📄 Looking for Financial Performance page...")

            # Try to find "Financial Performance" text or button
            try:
                # Check if we're already on Financial Performance page
                page_title = page.locator("h1, h2, h3").first
                title_text = page_title.text_content(timeout=5000) if page_title else ""

                if "Financial Performance" not in title_text:
                    # Try to navigate via sidebar or selectbox
                    # Streamlit might use radio buttons or selectbox for navigation
                    financial_option = page.get_by_text(
                        "Financial Performance", exact=False
                    )
                    if financial_option.is_visible(timeout=5000):
                        financial_option.click()
                        page.wait_for_timeout(2000)  # Wait for page to render

                print("   ✅ On Financial Performance page")

            except Exception as e:
                print(f"   ⚠️  Could not navigate to Financial Performance: {e}")
                print("   Assuming we're on the right page...")

            # Step 4: Find and verify Portfolio Value metric
            print("\n🔍 Looking for Portfolio Value metric...")

            # Streamlit metrics are typically in divs with specific classes
            # Look for text containing "Portfolio Value" and a dollar amount
            page_content = page.content()

            # Try multiple patterns to find the portfolio value
            patterns = [
                r'Portfolio Value["\s]*[<>:\w\s="\']*\$?([\d,]+\.?\d*)',
                r'Kalshi Balance["\s]*[<>:\w\s="\']*\$?([\d,]+\.?\d*)',
                r"\$\s*([\d,]+\.?\d*)\s*",  # Any dollar amount
            ]

            found_value = None
            for pattern in patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                if matches:
                    # Try to parse the first match
                    try:
                        value_str = matches[0].replace(",", "")
                        found_value = float(value_str)
                        print(f"   Found value: ${found_value:.2f}")
                        break
                    except Exception:
                        continue

            if found_value is None:
                print("   ❌ Could not find Portfolio Value on page")
                print("   Page might not be fully loaded or format changed")

                # Save screenshot for debugging
                screenshot_path = (
                    Path(__file__).parent.parent / "test_dashboard_screenshot.png"
                )
                page.screenshot(path=str(screenshot_path))
                print(f"   Screenshot saved to: {screenshot_path}")

                browser.close()
                return False

            # Step 5: Verify the value
            print("\n✅ Verification:")
            print(f"   Expected: ${expected_portfolio_value:.2f}")
            print(f"   Dashboard shows: ${found_value:.2f}")

            difference = abs(found_value - expected_portfolio_value)
            print(f"   Difference: ${difference:.2f}")

            if difference < 0.50:  # Within 50 cents
                print("\n✅ TEST PASSED! Dashboard shows correct portfolio value!")
                success = True
            else:
                print("\n❌ TEST FAILED! Values don't match")
                print("   This could be due to:")
                print("   - Race condition (bet settled during test)")
                print("   - Stale snapshot data")
                print("   - Dashboard calculation error")
                success = False

                # Save screenshot for debugging
                screenshot_path = (
                    Path(__file__).parent.parent / "test_dashboard_failure.png"
                )
                page.screenshot(path=str(screenshot_path))
                print(f"   Screenshot saved to: {screenshot_path}")

        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            success = False

        finally:
            browser.close()

    print("\n" + "=" * 80)
    return success


if __name__ == "__main__":
    print("=" * 80)
    print("Playwright Integration Test: Dashboard Portfolio Value")
    print("=" * 80)
    print("\nPrerequisites:")
    print("1. Dashboard must be running on http://localhost:8501")
    print("2. Playwright must be installed: pip install playwright")
    print("3. Playwright browsers must be installed: playwright install")
    print("=" * 80)

    success = test_financial_performance_shows_correct_portfolio_value()

    if success:
        print("\n✅ INTEGRATION TEST PASSED")
        sys.exit(0)
    else:
        print("\n❌ INTEGRATION TEST FAILED")
        sys.exit(1)
