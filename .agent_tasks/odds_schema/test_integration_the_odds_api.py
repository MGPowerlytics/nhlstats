"""Integration test: odds data schema validation in the live ingestion pipeline.

Tests that TheOddsAPI.save_to_db() correctly gates ingestion by validating
data against OddsFeedSchema before writing to the database.

Test scenarios:
1. Valid data → validation passes, data is saved, returns odds count > 0.
2. Bad odds (home_odds=0.5 < 1.01) → validation fails, returns 0.
3. Future commence_time → check_no_future_timestamps fails, returns 0.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add plugins/ to sys.path so imports resolve at runtime.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins"))

from the_odds_api import TheOddsAPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mock_game(
    *,
    sport: str = "nba",
    game_id: str = "game_nba_001",
    home_team: str = "Boston Celtics",
    away_team: str = "Los Angeles Lakers",
    commence_time: str = "2024-12-25T20:00:00Z",
    home_odds: float = 2.10,
    away_odds: float = 1.80,
    num_bookmakers: int = 3,
) -> dict:
    """Build a mock parsed game dict matching _parse_game() output format."""
    home_prob: float = 1.0 / home_odds if home_odds else 0.0
    away_prob: float = 1.0 / away_odds if away_odds else 0.0

    # Build one bookmaker entry per bookmaker count
    bookmakers: dict[str, dict] = {}
    for i in range(num_bookmakers):
        bm_name: str = f"bookmaker_{i}"
        bookmakers[bm_name] = {
            "home_odds": home_odds,
            "away_odds": away_odds,
            "home_prob": home_prob,
            "away_prob": away_prob,
            "last_update": "2024-01-01T00:00:00Z",
        }

    return {
        "platform": "odds_api",
        "sport": sport,
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "commence_time": commence_time,
        "bookmakers": bookmakers,
        "best_home_bookmaker": "bookmaker_0",
        "best_home_odds": home_odds,
        "best_home_prob": home_prob,
        "best_away_bookmaker": "bookmaker_0",
        "best_away_odds": away_odds,
        "best_away_prob": away_prob,
        "num_bookmakers": num_bookmakers,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client() -> TheOddsAPI:
    """Return a TheOddsAPI instance with a mock API key and mocked DB."""
    client = TheOddsAPI(api_key="test_key_12345")
    # Mock the database execute method so no real DB is needed
    client.db.execute = MagicMock(return_value=None)
    return client


# ============================================================================
#  Tests
# ============================================================================


class TestIngestionValidationGate:
    """Integration tests: validation gate inside save_to_db()."""

    # -- Happy path ----------------------------------------------------------

    def test_valid_data_saves_successfully(self, api_client: TheOddsAPI) -> None:
        """Given valid parsed markets, save_to_db() should validate, pass,
        write to DB, and return a positive odds count."""
        games: list[dict] = [
            _build_mock_game(
                sport="nba",
                game_id="NBA_20241225_CELTICS_LAKERS",
                home_team="Boston Celtics",
                away_team="Los Angeles Lakers",
                commence_time="2024-12-25T20:00:00Z",
                home_odds=2.10,
                away_odds=1.80,
                num_bookmakers=3,
            ),
            _build_mock_game(
                sport="nhl",
                game_id="NHL_20241226_BRUINS_CANADIENS",
                home_team="Boston Bruins",
                away_team="Montreal Canadiens",
                commence_time="2024-12-26T19:00:00Z",
                home_odds=1.95,
                away_odds=1.92,
                num_bookmakers=2,
            ),
        ]

        result: int = api_client.save_to_db(games)

        # Validation passed → data written → positive odds count
        assert result > 0, (
            f"Expected positive odds count for valid data, got {result}"
        )

    def test_fetch_and_save_markets_valid_data(self, api_client: TheOddsAPI) -> None:
        """Given valid mocked API data, fetch_and_save_markets() should
        return the number of games processed (pipeline succeeds)."""
        mock_games: list[dict] = [
            _build_mock_game(
                sport="nba",
                game_id="NBA_20241225_CELTICS_LAKERS",
                home_team="Boston Celtics",
                away_team="Los Angeles Lakers",
                commence_time="2024-12-25T20:00:00Z",
                home_odds=2.10,
                away_odds=1.80,
                num_bookmakers=3,
            ),
        ]

        with patch.object(api_client, "fetch_markets", return_value=mock_games):
            result: int = api_client.fetch_and_save_markets("nba", "2024-12-25")

        assert result == len(mock_games), (
            f"Expected {len(mock_games)} games saved, got {result}"
        )

    # -- Validation failure: bad odds ---------------------------------------

    def test_bad_odds_halt_ingestion(self, api_client: TheOddsAPI) -> None:
        """Given parsed markets with home_odds=0.5 (< 1.01), save_to_db()
        should halt and return 0 without writing to DB."""
        games: list[dict] = [
            _build_mock_game(
                sport="nba",
                game_id="NBA_20241225_CELTICS_LAKERS",
                home_team="Boston Celtics",
                away_team="Los Angeles Lakers",
                commence_time="2024-12-25T20:00:00Z",
                home_odds=0.5,  # ⛔ below MIN_ODDS (1.01)
                away_odds=1.80,
                num_bookmakers=3,
            ),
        ]

        result: int = api_client.save_to_db(games)

        assert result == 0, (
            f"Expected 0 (ingestion halted) for bad odds, got {result}"
        )
        # Verify that db.execute was NOT called (no data written)
        api_client.db.execute.assert_not_called()

    def test_bad_odds_fetch_and_save_halt(self, api_client: TheOddsAPI) -> None:
        """fetch_and_save_markets() with bad odds should return 0."""
        mock_games: list[dict] = [
            _build_mock_game(
                sport="nba",
                game_id="NBA_20241225_CELTICS_LAKERS",
                home_team="Boston Celtics",
                away_team="Los Angeles Lakers",
                commence_time="2024-12-25T20:00:00Z",
                home_odds=0.5,  # ⛔ below MIN_ODDS
                away_odds=1.80,
                num_bookmakers=3,
            ),
        ]

        with patch.object(api_client, "fetch_markets", return_value=mock_games):
            result: int = api_client.fetch_and_save_markets("nba", "2024-12-25")

        assert result == 0, (
            f"Expected 0 (ingestion halted) for bad odds, got {result}"
        )

    # -- Validation failure: future commence_time ---------------------------

    def test_future_commence_time_halt_ingestion(self, api_client: TheOddsAPI) -> None:
        """Given parsed markets with a future commence_time (year 2099),
        save_to_db() should halt and return 0."""
        games: list[dict] = [
            _build_mock_game(
                sport="nba",
                game_id="NBA_20990101_FUTURE_TEAM",
                home_team="Future Team A",
                away_team="Future Team B",
                commence_time="2099-01-01T12:00:00Z",  # ⛔ far in the future
                home_odds=2.10,
                away_odds=1.80,
                num_bookmakers=3,
            ),
        ]

        result: int = api_client.save_to_db(games)

        assert result == 0, (
            f"Expected 0 (ingestion halted) for future commence_time, got {result}"
        )
        api_client.db.execute.assert_not_called()

    def test_future_commence_time_fetch_and_save(self, api_client: TheOddsAPI) -> None:
        """fetch_and_save_markets() with future commence_time should return 0."""
        mock_games: list[dict] = [
            _build_mock_game(
                sport="nba",
                game_id="NBA_20990101_FUTURE_TEAM",
                home_team="Future Team A",
                away_team="Future Team B",
                commence_time="2099-01-01T12:00:00Z",
                home_odds=2.10,
                away_odds=1.80,
                num_bookmakers=3,
            ),
        ]

        with patch.object(api_client, "fetch_markets", return_value=mock_games):
            result: int = api_client.fetch_and_save_markets("nba", "2099-01-01")

        assert result == 0, (
            f"Expected 0 (ingestion halted) for future commence_time, got {result}"
        )

    # -- Edge case: empty markets -------------------------------------------

    def test_empty_markets_returns_zero(self, api_client: TheOddsAPI) -> None:
        """save_to_db([]) should return 0 without validation or DB writes."""
        result: int = api_client.save_to_db([])

        assert result == 0
        api_client.db.execute.assert_not_called()

    def test_no_mock_data_returns_zero(self, api_client: TheOddsAPI) -> None:
        """fetch_and_save_markets with no (empty) mock should return 0."""
        with patch.object(api_client, "fetch_markets", return_value=[]):
            result: int = api_client.fetch_and_save_markets("nba", "2024-12-25")

        assert result == 0


class TestSchemaImportableFromPlugins:
    """Verify odds_data_schema is importable from plugins/ at runtime."""

    def test_schema_importable(self) -> None:
        """The OddsFeedSchema class should be importable from
        plugins.odds_data_schema."""
        from plugins.odds_data_schema import OddsFeedSchema
        assert OddsFeedSchema is not None

    def test_validate_function_importable(self) -> None:
        """validate_odds_dataframe should be importable from
        plugins.odds_data_schema."""
        from plugins.odds_data_schema import validate_odds_dataframe
        assert callable(validate_odds_dataframe)
