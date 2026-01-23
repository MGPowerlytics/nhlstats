"""
Playwright tests for Financial Performance dashboard page.

Tests the Portfolio Value metric calculation:
- Portfolio Value = Cash Balance + Open Positions Value
- Verifies displayed value matches database query
"""

import pytest
from playwright.sync_api import Page, expect
import time
import re
from decimal import Decimal


@pytest.fixture(scope="module")
def dashboard_url():
    """Return the URL of the running dashboard container."""
    url = "http://localhost:8501"
    time.sleep(2)
    yield url


@pytest.fixture(scope="function")
def page(dashboard_url, playwright):
    """Create a new page for each test."""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")
    time.sleep(5)  # Wait for initial render

    yield page

    context.close()
    browser.close()


class TestFinancialPerformancePortfolioValue:
    """Test Portfolio Value metric on Financial Performance page."""

    def test_financial_performance_page_loads(self, page: Page):
        """Test Financial Performance page loads with title and metrics."""
        # Navigate to Financial Performance using sidebar radio button
        page.get_by_text("Financial Performance", exact=True).click()
        time.sleep(6)  # Wait for page transition and metrics to load

        # Verify page title exists
        title_exists = page.locator('text="💰 Financial Performance"').count() > 0
        assert title_exists, "Financial Performance page title not found"

        # Verify metrics are displayed
        metrics = page.locator('[data-testid="stMetric"]')
        assert metrics.count() > 0, "No metrics found on Financial Performance page"

    def test_portfolio_value_metric_visible(self, page: Page):
        """Test Portfolio Value metric label and value are visible."""
        # Navigate to Financial Performance using sidebar radio button
        page.get_by_text("Financial Performance", exact=True).click()
        time.sleep(6)  # Wait for page transition and metrics to load

        # Check for Portfolio Value label
        portfolio_label = page.locator('text="Portfolio Value"')
        assert portfolio_label.count() > 0, "Portfolio Value label not found"

        # Check for metric values with correct data-testid
        metric_values = page.locator('[data-testid="stMetricValue"]')
        assert metric_values.count() > 0, "No metric values found with data-testid='stMetricValue'"

    def test_portfolio_value_equals_cash_plus_bets(self, page: Page):
        """Test displayed Portfolio Value equals cash balance + open positions value.

        This is the main TDD test. Portfolio Value should equal:
        - Cash balance (from portfolio_value_snapshots table)
        - Plus open positions value (sum of cost_dollars from placed_bets where status='open')
        """
        # Arrange: Calculate expected portfolio value from database
        from plugins.db_manager import DBManager
        import os

        # Override postgres host to localhost for tests running outside Docker
        os.environ["POSTGRES_HOST"] = "localhost"
        db = DBManager()

        # Get latest cash balance from portfolio_value_snapshots
        cash_df = db.fetch_df(
            """
            SELECT ROUND(balance_dollars::numeric, 2) as cash_balance
            FROM portfolio_value_snapshots
            ORDER BY snapshot_hour_utc DESC
            LIMIT 1
            """
        )

        # Get value of open positions
        open_bets_df = db.fetch_df(
            """
            SELECT ROUND(SUM(cost_dollars)::numeric, 2) as open_positions_value
            FROM placed_bets
            WHERE status = 'open'
            """
        )

        if cash_df.empty:
            pytest.skip("No portfolio value snapshots in database")

        cash_balance = float(cash_df.iloc[0]["cash_balance"])
        open_value = (
            float(open_bets_df.iloc[0]["open_positions_value"])
            if not open_bets_df.empty and open_bets_df.iloc[0]["open_positions_value"]
            else 0.0
        )
        expected_portfolio_value = cash_balance + open_value

        # Act: Navigate to Financial Performance and extract displayed Portfolio Value
        page.get_by_text("Financial Performance", exact=True).click()
        time.sleep(6)  # Wait for page transition and metrics to load

        # Debug: Save screenshot and page content
        page.screenshot(path="/tmp/financial_performance_debug.png")
        page_content = page.content()
        with open("/tmp/financial_performance_content.html", "w") as f:
            f.write(page_content)

        # Find Portfolio Value metric
        # Look for the stMetric that contains "Portfolio Value" text
        portfolio_metrics = page.locator('[data-testid="stMetric"]')

        print(f"\n🔍 DEBUG: Found {portfolio_metrics.count()} metrics on page")

        displayed_value = None
        metric_label = None
        for i in range(portfolio_metrics.count()):
            metric = portfolio_metrics.nth(i)
            metric_text = metric.inner_text()
            print(f"  Metric {i}: {metric_text[:100]}")

            # Check if this metric contains "Portfolio Value"
            if "Portfolio Value" in metric_text:
                metric_label = "Portfolio Value"
                print(f"  ✓ Found Portfolio Value metric!")

                # Extract the dollar value from stMetricValue within this metric
                value_element = metric.locator('[data-testid="stMetricValue"]')
                if value_element.count() > 0:
                    value_text = value_element.inner_text()
                    print(f"  Value text: {value_text}")
                    # Extract numeric value (e.g., "$80.69" -> 80.69)
                    match = re.search(r'\$?([0-9,]+\.[0-9]{2})', value_text)
                    if match:
                        displayed_value = float(match.group(1).replace(',', ''))
                        print(f"  Extracted value: ${displayed_value:.2f}")
                        break

        # Assert: Must find Portfolio Value metric (no fallback)
        assert displayed_value is not None, (
            "Portfolio Value metric not found! Dashboard should always show Portfolio Value "
            "(cash + open bets) from portfolio_value_snapshots table, not a fallback."
        )
        assert metric_label == "Portfolio Value", (
            f"Expected 'Portfolio Value' metric but found '{metric_label}'. "
            "Dashboard should not show 'Total Invested' fallback."
        )

        # Allow small tolerance ($0.05) for timing differences between DB query and page render
        tolerance = 0.05
        diff = abs(displayed_value - expected_portfolio_value)

        assert diff <= tolerance, (
            f"Portfolio Value mismatch: "
            f"displayed=${displayed_value:.2f}, "
            f"expected=${expected_portfolio_value:.2f} "
            f"(cash=${cash_balance:.2f} + open_bets=${open_value:.2f}), "
            f"difference=${diff:.2f}"
        )
