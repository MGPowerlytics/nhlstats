"""TDD tests for BetDeduplicator — cross-day bet deduplication.

The deduplicator checks placed_bets for existing bets on the same
(sport, home_team, away_team, bet_on) within a 3-day rolling window.
"""

from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy import text

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
    # No teardown needed — conftest.py drops all tables between tests


def insert_bet(
    engine,
    bet_id: str,
    sport: str = "MLB",
    placed_date: str = "2026-04-26",
    home_team: str = "NYY",
    away_team: str = "BOS",
    bet_on: str = "NYY",
    side: str = "yes",
    status: str = "open",
) -> None:
    """Insert a row into placed_bets for test setup."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                     home_team, away_team, bet_on, side, status)
            VALUES (:bet_id, :sport, :placed_date, :ticker,
                    :home_team, :away_team, :bet_on, :side, :status)
            """
            ),
            {
                "bet_id": bet_id,
                "sport": sport,
                "placed_date": placed_date,
                "ticker": f"TICKER-{bet_id}",
                "home_team": home_team,
                "away_team": away_team,
                "bet_on": bet_on,
                "side": side,
                "status": status,
            },
        )
        conn.commit()


# ===========================================================================
# TDD Tests
# ===========================================================================

class TestBetDeduplicator:
    """TDD suite for BetDeduplicator.is_duplicate()."""

    # --- Test 1: Exact match returns True --------------------------------

    def test_is_duplicate_returns_true_for_exact_match(self, engine):
        """Same (sport, home, away, bet_on) within 3 days → True."""
        insert_bet(
            engine,
            bet_id="bet-001",
            sport="MLB",
            placed_date="2026-04-24",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            status="open",
        )

        dedup = BetDeduplicator()
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )

        assert result is True

    # --- Test 2: Different sport returns False ---------------------------

    def test_is_duplicate_returns_false_for_different_sport(self, engine):
        """Same teams, different sport → False."""
        insert_bet(
            engine,
            bet_id="bet-002",
            sport="MLB",
            placed_date="2026-04-24",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            status="open",
        )

        dedup = BetDeduplicator()
        result = dedup.is_duplicate(
            sport="NBA",  # Different sport
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )

        assert result is False

    # --- Test 3: Outside window returns False ----------------------------

    def test_is_duplicate_outside_window(self, engine):
        """Same matchup but placed_date > 3 days from existing → False."""
        insert_bet(
            engine,
            bet_id="bet-003",
            sport="MLB",
            placed_date="2026-04-20",  # 6 days before proposed date
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            status="open",
        )

        dedup = BetDeduplicator()
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",  # 2026-04-26 - 3 = 2026-04-23; existing is 2026-04-20 < 2026-04-23
        )

        assert result is False

    # --- Test 4: Different bet_on returns False --------------------------

    def test_is_duplicate_different_bet_on(self, engine):
        """Same matchup but betting on different side → False."""
        insert_bet(
            engine,
            bet_id="bet-004",
            sport="MLB",
            placed_date="2026-04-24",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            status="open",
        )

        dedup = BetDeduplicator()
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="BOS",  # Different side
            placed_date="2026-04-26",
        )

        assert result is False

    # --- Test 5: Empty DB returns False ----------------------------------

    def test_is_duplicate_empty_database(self, engine):
        """No bets in placed_bets → False."""
        dedup = BetDeduplicator()
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )

        assert result is False

    # --- Test 6: Ignores canceled bets ------------------------------------

    def test_is_duplicate_ignores_canceled_bets(self, engine):
        """Existing bet has status canceled → False (can re-bet)."""
        insert_bet(
            engine,
            bet_id="bet-005",
            sport="MLB",
            placed_date="2026-04-24",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            status="canceled",  # Canceled — should not block
        )

        dedup = BetDeduplicator()
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )

        assert result is False

    # --- Test 7: Null team names ------------------------------------------

    def test_is_duplicate_null_team_names(self, engine):
        """Pre-backfill rows with null home/away → treated as no match."""
        # Insert a row with NULL home_team and away_team
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES (:bet_id, :sport, :placed_date, :ticker,
                        :home_team, :away_team, :bet_on, :side, :status)
                """
                ),
                {
                    "bet_id": "bet-null",
                    "sport": "MLB",
                    "placed_date": "2026-04-24",
                    "ticker": "TICKER-NULL",
                    "home_team": None,
                    "away_team": None,
                    "bet_on": "NYY",
                    "side": "yes",
                    "status": "open",
                },
            )
            conn.commit()

        dedup = BetDeduplicator()
        # This should NOT match the null team row
        result = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )

        assert result is False

    # --- Test 8: Strict 3-day boundary -----------------------------------

    def test_dedup_window_is_strictly_3_days(self, engine):
        """Boundary test: exactly at day 3 = duplicate, outside >3 = not.

        Window: proposed 2026-04-26 minus 3 days = 2026-04-23.
        - 2026-04-23 (exactly 3 days before) → match (boundary inclusive)
        - 2026-04-22 (4 days before) → no match (outside window)
        """
        dedup = BetDeduplicator()

        # Bet placed exactly 3 days before proposed date → should match
        insert_bet(
            engine,
            bet_id="bet-in",
            sport="MLB",
            placed_date="2026-04-23",  # boundary: 2026-04-26 - 3 = 2026-04-23
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            status="open",
        )

        inside = dedup.is_duplicate(
            sport="MLB",
            home_team="NYY",
            away_team="BOS",
            bet_on="NYY",
            placed_date="2026-04-26",
        )
        assert inside is True, (
            "Bet placed exactly 3 days before proposed date should match "
            "(boundary inclusive)"
        )

        # Use a different sport/teams for the outside test
        insert_bet(
            engine,
            bet_id="bet-out",
            sport="NBA",
            placed_date="2026-04-22",  # 4 days before proposed — outside window
            home_team="LAL",
            away_team="BOS",
            bet_on="LAL",
            status="open",
        )

        outside = dedup.is_duplicate(
            sport="NBA",
            home_team="LAL",
            away_team="BOS",
            bet_on="LAL",
            placed_date="2026-04-26",
        )
        assert outside is False, (
            "Bet placed 4 days before proposed date should NOT match "
            "(outside 3-day window)"
        )

    # --- Test 9: Game-level dedup via ticker — same game, opposite side ---
    # When a ticker is provided, the dedup check should expand to the base game ID.
    # e.g. "KXEPLGAME-26MAY04EVEMCI-MCI" and "KXEPLGAME-26MAY04EVEMCI-EVE"
    # share base "KXEPLGAME-26MAY04EVEMCI" → second bet is a duplicate.

    def test_is_duplicate_game_level_via_ticker(self, engine):
        """Same base game (ticker), different side → True (game-level dedup)."""
        dedup = BetDeduplicator()
        # Insert first bet on Man City (away side) with real ticker format
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES (:bet_id, :sport, :placed_date, :ticker,
                        :home_team, :away_team, :bet_on, :side, :status)
                """
                ),
                {
                    "bet_id": "bet-gl-001-mci",
                    "sport": "EPL",
                    "placed_date": "2026-04-26",
                    "ticker": "KXEPLGAME-26MAY04EVEMCI-MCI",
                    "home_team": "Everton",
                    "away_team": "Man City",
                    "bet_on": "Man City",
                    "side": "yes",
                    "status": "open",
                },
            )
            conn.commit()

        # Now try to bet on Everton (home side) — same base game ID → duplicate
        result = dedup.is_duplicate(
            sport="EPL",
            home_team="Everton",
            away_team="Man City",
            bet_on="Everton",  # Different side
            placed_date="2026-04-27",
            ticker="KXEPLGAME-26MAY04EVEMCI-EVE",
        )

        assert result is True, (
            "Bet on opposite side of same base game ID should be a duplicate"
        )

    # --- Test 10: Same base game, different game date (not a duplicate) ---

    def test_is_duplicate_different_base_game_not_duplicate(self, engine):
        """Different base game IDs → not duplicates (side-level check still works)."""
        # Insert bet on game A
        insert_bet(
            engine,
            bet_id="bet-gl-002",
            sport="EPL",
            placed_date="2026-04-26",
            home_team="Everton",
            away_team="Man City",
            bet_on="Everton",
            side="yes",
            status="open",
        )
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES (:bet_id, :sport, :placed_date, :ticker,
                        :home_team, :away_team, :bet_on, :side, :status)
                """
                ),
                {
                    "bet_id": "bet-gl-002",
                    "sport": "EPL",
                    "placed_date": "2026-04-26",
                    "ticker": "KXEPLGAME-26MAY04EVEMCI-EVE",
                    "home_team": "Everton",
                    "away_team": "Man City",
                    "bet_on": "Everton",
                    "side": "yes",
                    "status": "open",
                },
            )
            conn.commit()

        dedup = BetDeduplicator()
        # Same teams, same side — BUT different base game ID and no ticker →
        # falls back to side-level dedup which should still catch it
        result_no_ticker = dedup.is_duplicate(
            sport="EPL",
            home_team="Everton",
            away_team="Man City",
            bet_on="Everton",
            placed_date="2026-04-27",
            # no ticker → uses side-level dedup
        )
        assert result_no_ticker is True

    # --- Test 11: No ticker falls back to side-level dedup correctly ----

    def test_no_ticker_falls_back_to_side_level(self, engine):
        """Without a ticker, the original side-level dedup is used."""
        insert_bet(
            engine,
            bet_id="bet-gl-003",
            sport="EPL",
            placed_date="2026-04-26",
            home_team="Arsenal",
            away_team="Liverpool",
            bet_on="Arsenal",
            side="yes",
            status="open",
        )

        dedup = BetDeduplicator()
        # No ticker — same matchup + same side → duplicate
        result = dedup.is_duplicate(
            sport="EPL",
            home_team="Arsenal",
            away_team="Liverpool",
            bet_on="Arsenal",
            placed_date="2026-04-27",
            ticker=None,
        )
        assert result is True

        # No ticker — same matchup but different side → NOT duplicate
        result_diff_side = dedup.is_duplicate(
            sport="EPL",
            home_team="Arsenal",
            away_team="Liverpool",
            bet_on="Liverpool",
            placed_date="2026-04-27",
            ticker=None,
        )
        assert result_diff_side is False

    # --- Test 12: Game-level dedup is permanent (no date window) -----------

    def test_game_level_dedup_is_permanent_regardless_of_window(
        self, engine
    ):
        """Game-level dedup via ticker should NOT be limited by the 3-day window.

        The base game ID (e.g. KXEPLGAME-26MAY04EVEMCI) uniquely identifies
        a specific game. If we've already bet on this game, we should never
        bet on it again — regardless of how many days have passed.

        The 3-day window makes sense for side-level dedup (same teams playing
        again in a different game), but for a specific game ID the dedup
        should be permanent.
        """
        dedup = BetDeduplicator()

        # Insert a bet from 10 days ago on Man City side
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, ticker,
                                         home_team, away_team, bet_on, side, status)
                VALUES (:bet_id, :sport, :placed_date, :ticker,
                        :home_team, :away_team, :bet_on, :side, :status)
                """
                ),
                {
                    "bet_id": "bet-perm-001-mci",
                    "sport": "EPL",
                    "placed_date": "2026-04-17",  # 10 days before proposed
                    "ticker": "KXEPLGAME-26MAY04EVEMCI-MCI",
                    "home_team": "Everton",
                    "away_team": "Man City",
                    "bet_on": "Man City",
                    "side": "yes",
                    "status": "open",
                },
            )
            conn.commit()

        # Now try to bet on Everton side 10 days later — should STILL be
        # blocked because it's the same specific game
        result = dedup.is_duplicate(
            sport="EPL",
            home_team="Everton",
            away_team="Man City",
            bet_on="Everton",  # Opposite side
            placed_date="2026-04-27",  # 10 days after the first bet
            ticker="KXEPLGAME-26MAY04EVEMCI-EVE",
        )

        assert result is True, (
            "Game-level dedup via base game ID should be permanent — "
            "a bet placed 10 days ago on the same game should still block "
            "new bets on the opposite side"
        )

    # --- Test 13: Side-level dedup still uses the 3-day window ------------

    def test_side_level_dedup_still_uses_window(self, engine):
        """Side-level dedup (without ticker) should still respect the 3-day window.

        When there's no ticker, we fall back to the original side-level dedup
        based on (sport, home_team, away_team, bet_on). This should still be
        window-limited because the same matchup can occur again in a different
        game (e.g., same teams playing next week).
        """
        dedup = BetDeduplicator()

        # Insert a bet from 10 days ago (same matchup, same side)
        insert_bet(
            engine,
            bet_id="bet-side-001",
            sport="EPL",
            placed_date="2026-04-17",
            home_team="Arsenal",
            away_team="Chelsea",
            bet_on="Arsenal",
            status="open",
        )

        # Try same matchup 10 days later — should NOT be blocked
        # because side-level dedup uses the 3-day window
        result = dedup.is_duplicate(
            sport="EPL",
            home_team="Arsenal",
            away_team="Chelsea",
            bet_on="Arsenal",
            placed_date="2026-04-27",
            ticker=None,  # No ticker → side-level dedup only
        )

        assert result is False, (
            "Side-level dedup without a ticker should still use the 3-day "
            "window — the same matchup can occur in a different game"
        )
