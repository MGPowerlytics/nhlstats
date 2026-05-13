"""Seeded Playwright E2E coverage for the governed Streamlit dashboard.

The default pytest path quarantines these browser tests.  When
``RUN_DASHBOARD_E2E=1`` is set, this module provisions an isolated PostgreSQL
schema, applies the in-repo dashboard migrations, seeds deterministic fixture
rows, launches Streamlit against that schema, and asserts every current
dashboard page renders meaningful seeded content.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

RUN_DASHBOARD_E2E = bool(os.environ.get("RUN_DASHBOARD_E2E"))

try:
    from playwright.sync_api import Page, expect
except ModuleNotFoundError:
    if RUN_DASHBOARD_E2E:
        raise
    pytest.skip(
        "Dashboard Playwright tests require the optional playwright dependency",
        allow_module_level=True,
    )

from plugins.db_manager import DBManager
from plugins.schema_migrations import SchemaMigrationRunner
from tests.contracts.fixtures.dashboard_seed_samples import (
    build_dashboard_source_seed_payload,
    seed_dashboard_source_rows,
)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not RUN_DASHBOARD_E2E,
        reason=(
            "Seeded dashboard Playwright tests are quarantined from default pytest. "
            "Set RUN_DASHBOARD_E2E=1 to run the non-skipping validation path."
        ),
    ),
]

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_APP = REPO_ROOT / "dashboard" / "app.py"
SEEDED_BET_ID = "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME"


def _build_connection_string() -> str:
    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "airflow")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_dashboard(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 90
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Streamlit exited early with code {process.returncode}"
            ) from last_error
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001 - surfaced on timeout
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for Streamlit at {url}") from last_error


def _navigate(page: Page, label: str) -> None:
    page.get_by_text(label, exact=True).click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)
    _assert_rendered_page(page, label)


def _assert_rendered_page(page: Page, page_name: str) -> None:
    expect(page.locator('[data-testid="stApp"]')).to_be_visible()
    exception_count = page.locator('[data-testid="stException"]').count()
    assert exception_count == 0, f"{page_name} rendered a Streamlit exception"
    body_text = page.locator("body").inner_text()
    assert len(body_text.strip()) >= 80, f"{page_name} rendered a blank/useless page"


def _assert_text(page: Page, text_value: str) -> None:
    locator = page.get_by_text(text_value, exact=False)
    if locator.count() == 0:
        body_text = page.locator("body").inner_text()
        assert text_value in body_text
        return
    first_match = locator.first
    if not first_match.is_visible():
        assert locator.count() > 0
        return
    expect(first_match).to_be_visible()


def _select_sport(page: Page, current_sport: str, target_sport: str) -> None:
    if current_sport == target_sport:
        return
    page.get_by_text(current_sport, exact=True).click()
    page.get_by_role("option", name=target_sport).click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)


@pytest.fixture(scope="module")
def dashboard_schema() -> Iterator[str]:
    """Create a migrated PostgreSQL schema containing only deterministic seeds."""

    base_connection_string = _build_connection_string()
    schema_name = f"dashboard_e2e_{uuid.uuid4().hex}"
    try:
        admin_engine = create_engine(base_connection_string)
        with admin_engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema_name}"))
    except Exception as exc:  # noqa: BLE001 - fail, do not skip, when E2E is enabled
        pytest.fail(f"Could not create isolated PostgreSQL schema: {exc}")

    db = DBManager(connection_string=base_connection_string, schema=schema_name)
    try:
        runner = SchemaMigrationRunner(db)
        runner.apply()
        runner.assert_verified()
        seed_dashboard_source_rows(db, build_dashboard_source_seed_payload())
        yield schema_name
    finally:
        db.engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        admin_engine.dispose()


@pytest.fixture(scope="module")
def dashboard_url(dashboard_schema: str) -> Iterator[str]:
    """Launch Streamlit against the isolated schema and return its local URL."""

    port = _reserve_port()
    url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "POSTGRES_SCHEMA": dashboard_schema,
        "DASHBOARD_DISABLE_AUTO_REFRESH": "1",
        "STREAMLIT_SERVER_HEADLESS": "true",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    }
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(DASHBOARD_APP),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError as exc:
        pytest.fail(f"Could not launch Streamlit: {exc}")

    try:
        _wait_for_dashboard(url, process)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15)


@pytest.fixture()
def page(dashboard_url: str, playwright: Any) -> Iterator[Page]:
    """Open a fresh browser page for each seeded dashboard scenario."""

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1100})
    page = context.new_page()
    page.set_default_timeout(45_000)
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)
    yield page
    context.close()
    browser.close()


class TestSeededDashboardPages:
    """Semantic seeded-data assertions for every current dashboard page."""

    def test_portfolio_page_renders_seeded_kpis(self, page: Page) -> None:
        _assert_rendered_page(page, "Portfolio")
        _assert_text(page, "Portfolio Overview")
        _assert_text(page, "Portfolio Value")
        _assert_text(page, "$1,475.75")
        _assert_text(page, "Position Summary")
        _assert_text(page, "Governed open exposure totals")
        _assert_text(page, "executed-unsettled exposure")

    def test_live_markets_page_renders_seeded_market(self, page: Page) -> None:
        _navigate(page, "Live Markets")
        _assert_text(page, "Governed Live Markets")
        _assert_text(page, "New York Rangers")
        _assert_text(page, "Boston Bruins")
        _assert_text(page, "KXNHL-26MAY03NYRBOS-NYR")

    def test_rankings_page_renders_seeded_nhl_rankings(self, page: Page) -> None:
        _navigate(page, "Rankings")
        _select_sport(page, "NBA", "NHL")
        _assert_text(page, "Elo Rankings")
        _assert_text(page, "NHL Ratings (2 active rows)")
        _assert_text(page, "New York Rangers")
        _assert_text(page, "Boston Bruins")
        _assert_text(page, "Head-to-Head Prediction")

    def test_calibration_page_renders_seeded_bucket(self, page: Page) -> None:
        _navigate(page, "Calibration")
        _assert_text(page, "Model Calibration")
        _assert_text(page, "Probability Buckets")
        _assert_text(page, "60%-70%")
        _assert_text(page, "No governed settled outcomes are available yet.")

    def test_calibration_page_surfaces_blocked_sport_state(self, page: Page) -> None:
        _navigate(page, "Calibration")
        _select_sport(page, "All", "NBA")
        _assert_text(page, "Governed Sport Validation")
        _assert_text(
            page,
            "NBA remains blocked because no repeatable approval-grade validation path is currently governed.",
        )

    def test_calibration_page_surfaces_shadow_only_contamination(
        self, page: Page
    ) -> None:
        _navigate(page, "Calibration")
        _select_sport(page, "All", "TENNIS")
        _assert_text(page, "Governed Sport Validation")
        _assert_text(page, "TENNIS is shadow-only")
        _assert_text(
            page,
            "binary_result_clv_contamination;synthetic_ticker_contamination",
        )

    def test_data_quality_page_renders_seeded_checks(self, page: Page) -> None:
        _navigate(page, "Data Quality")
        _assert_text(page, "Data Quality")
        _assert_text(page, "Overall Health Score")
        _assert_text(page, "Governed Data Quality Checks")
        _assert_text(page, "portfolio_value_snapshots")
        _assert_text(page, "dashboard_bet_detail_v1")

    def test_bet_detail_page_renders_seeded_traceability(
        self, page: Page, dashboard_url: str
    ) -> None:
        page.goto(f"{dashboard_url}/?bet_id={SEEDED_BET_ID}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        _assert_rendered_page(page, "Bet Detail")
        _assert_text(page, f"Bet Detail: {SEEDED_BET_ID}")
        _assert_text(page, "New York Rangers vs Boston Bruins")
        _assert_text(page, "62.0%")
        _assert_text(page, "KXNHL-26MAY03NYRBOS-NYR")
        _assert_text(page, "Traceability")
        _assert_text(page, "Linkage status")
        _assert_text(page, "Selected close rule")


class TestSeededDashboardEmptyStates:
    """Explicit state assertions for practical no-data/not-found paths."""

    def test_rankings_empty_state_for_unseeded_sport_is_explicit(
        self, page: Page
    ) -> None:
        _navigate(page, "Rankings")
        _assert_rendered_page(page, "Rankings empty state")
        _assert_text(page, "No rankings")
        _assert_text(page, "Run rating ingestion before comparing teams.")

    def test_bet_detail_not_found_state_is_explicit(
        self, page: Page, dashboard_url: str
    ) -> None:
        page.goto(f"{dashboard_url}/?bet_id=NOT-A-SEEDED-BET")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        _assert_rendered_page(page, "Bet Detail not found")
        _assert_text(page, "Bet not found")
        _assert_text(page, "Selected bet: NOT-A-SEEDED-BET")
