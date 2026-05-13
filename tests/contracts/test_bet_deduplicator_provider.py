"""Provider contract tests for the BetDeduplicator boundary.

These tests verify the contractual invariants of the
:class:`BetDeduplicator.is_duplicate` interface:

1. Returns ``bool`` for all valid inputs.
2. Handles edge cases (empty DB, null teams, canceled status).
3. Window boundary is strictly 3 calendar days (inclusive).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from plugins.bet_deduplicator import BetDeduplicator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Get the shared test engine from default_db."""
    from db_manager import default_db
    return default_db.engine


@pytest.fixture(autouse=True)
def create_placed_bets_table(engine):
    """Ensure placed_bets table exists for each test."""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS placed_bets (
                bet_id VARCHAR PRIMARY KEY,
                sport VARCHAR,
                placed_date DATE,
                ticker VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                bet_on VARCHAR,
                side VARCHAR,
                status VARCHAR
            )
            """
            )
        )
        conn.commit()
    yield


@pytest.fixture
def dedup() -> BetDeduplicator:
    """A fresh BetDeduplicator instance."""
    return BetDeduplicator()


# ===========================================================================
# Contract tests
# ===========================================================================

class TestBetDeduplicatorProviderContract:
    """Provider-side guarantees for the BetDeduplicator boundary."""

    # --- Contract 1: Return type is bool ----------------------------------

    def test_contract_returns_bool(self, dedup, engine) -> None:
        """is_duplicate must return a Python bool for all valid inputs."""
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )
        assert isinstance(result, bool), (
            f"Expected bool, got {type(result).__name__}"
        )

    # --- Contract 2: Empty DB returns False --------------------------------

    def test_contract_empty_db_returns_false(self, dedup) -> None:
        """With no data in placed_bets, is_duplicate must return False."""
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )
        assert result is False

    # --- Contract 3: Null team names do not match --------------------------

    def test_contract_null_team_names_no_match(self, dedup, engine) -> None:
        """Rows with NULL home_team/away_team must not match real team names."""
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES ('null-row', 'MLB', '2026-04-24', 'TICKER',
                        NULL, NULL, 'NYY', 'yes', 'open')
                """
                )
            )
            conn.commit()

        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )
        assert result is False, (
            "Null team names should not match canonical team names"
        )

    # --- Contract 4: Canceled status is ignored ----------------------------

    def test_contract_canceled_bets_ignored(self, dedup, engine) -> None:
        """Bets with status='canceled' must not block a new bet."""
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES ('canceled-row', 'MLB', '2026-04-24', 'TICKER',
                        'NYY', 'BOS', 'NYY', 'yes', 'canceled')
                """
                )
            )
            conn.commit()

        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )
        assert result is False, (
            "Canceled bets should not block new bets on the same matchup"
        )

    # --- Contract 5: Sport scoping -----------------------------------------

    def test_contract_sport_scoping(self, dedup, engine) -> None:
        """Same teams under different sport codes must not collide."""
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES ('sport-scope', 'EPL', '2026-04-24', 'TICKER',
                        'Arsenal', 'Chelsea', 'Arsenal', 'yes', 'open')
                """
                )
            )
            conn.commit()

        # Same teams but different sport
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="Arsenal",
            away_team="Chelsea",
            bet_on="Arsenal",
            placed_date="2026-04-26",
        )
        assert result is False, (
            "Same teams under different sport must not be duplicates"
        )

        # Same sport should match
        result_same_sport = dedup.is_duplicate(
            sport="EPL",
            home_team="Arsenal",
            away_team="Chelsea",
            bet_on="Arsenal",
            placed_date="2026-04-26",
        )
        assert result_same_sport is True, (
            "Same teams under same sport must be duplicates"
        )

    # --- Contract 6: Window scoping ----------------------------------------

    def test_contract_window_scoping(self, dedup, engine) -> None:
        """Bets outside the 3-day window must return False."""
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES ('old-bet', 'MLB', '2026-04-19', 'TICKER',
                        'NYY', 'BOS', 'NYY', 'yes', 'open')
                """
                )
            )
            conn.commit()

        # Proposed 2026-04-26, window starts at 2026-04-23
        # Existing bet is 2026-04-19, outside window
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )
        assert result is False, (
            "Bets placed more than 3 days before proposed date must not match"
        )
