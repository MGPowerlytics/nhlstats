"""Tests for CLV (Closing Line Value) fix — real closing prices from game_odds."""

import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import text
from db_manager import default_db


def _engine():
    """Get the test engine from the patched default_db."""
    return default_db.engine


# Helper to create test tables matching production schema
def create_test_tables(engine):
    """Create placed_bets, unified_games, and game_odds tables for testing."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS placed_bets (
                bet_id VARCHAR PRIMARY KEY,
                sport VARCHAR,
                placed_date DATE,
                placed_time_utc TIMESTAMP,
                ticker VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                bet_on VARCHAR,
                side VARCHAR,
                contracts INTEGER,
                price_cents INTEGER,
                cost_dollars REAL,
                fees_dollars REAL,
                elo_prob REAL,
                market_prob REAL,
                edge REAL,
                expected_value REAL,
                kelly_fraction REAL,
                confidence VARCHAR,
                market_title VARCHAR,
                market_close_time_utc TIMESTAMP,
                opening_line_prob REAL,
                bet_line_prob REAL,
                closing_line_prob REAL,
                clv REAL,
                status VARCHAR,
                settled_date DATE,
                payout_dollars REAL,
                profit_dollars REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS unified_games (
                game_id VARCHAR PRIMARY KEY,
                sport VARCHAR NOT NULL,
                game_date DATE NOT NULL,
                season INTEGER,
                status VARCHAR,
                home_team_id VARCHAR,
                home_team_name VARCHAR,
                away_team_id VARCHAR,
                away_team_name VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                commence_time TIMESTAMP,
                venue VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS game_odds (
                odds_id VARCHAR PRIMARY KEY,
                game_id VARCHAR NOT NULL,
                bookmaker VARCHAR NOT NULL,
                market_name VARCHAR NOT NULL,
                outcome_name VARCHAR,
                price REAL NOT NULL,
                line REAL,
                last_update TIMESTAMP,
                is_pregame INTEGER DEFAULT 1,
                external_id VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        conn.commit()


def insert_test_bet(
    engine,
    bet_id,
    sport="NBA",
    home_team="BOS",
    away_team="LAL",
    bet_on="home",
    side="yes",
    placed_date="2026-02-15",
    market_close_time="2026-02-15 23:00:00",
    closing_line_prob=1.0,
    clv=0.3,
    status="won",
    bet_line_prob=0.65,
    profit_dollars=5.0,
):
    """Insert a test bet with binary CLV (the bug)."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            INSERT INTO placed_bets (bet_id, sport, placed_date, home_team, away_team,
                bet_on, side, market_close_time_utc, closing_line_prob, clv, status,
                bet_line_prob, profit_dollars, price_cents, cost_dollars, contracts)
            VALUES (:bet_id, :sport, :placed_date, :home_team, :away_team,
                :bet_on, :side, :market_close_time, :closing_line_prob, :clv, :status,
                :bet_line_prob, :profit_dollars, 65, 6.5, 1)
        """
            ),
            {
                "bet_id": bet_id,
                "sport": sport,
                "placed_date": placed_date,
                "home_team": home_team,
                "away_team": away_team,
                "bet_on": bet_on,
                "side": side,
                "market_close_time": market_close_time,
                "closing_line_prob": closing_line_prob,
                "clv": clv,
                "status": status,
                "bet_line_prob": bet_line_prob,
                "profit_dollars": profit_dollars,
            },
        )
        conn.commit()


def insert_test_game(
    engine,
    game_id,
    sport="nba",
    game_date="2026-02-15",
    home_team="BOS",
    away_team="LAL",
    commence_time="2026-02-15 19:00:00",
):
    """Insert a test game in unified_games."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            INSERT INTO unified_games (game_id, sport, game_date, home_team_name,
                away_team_name, commence_time, home_score, away_score, status)
            VALUES (:game_id, :sport, :game_date, :home_team, :away_team,
                :commence_time, 110, 100, 'completed')
        """
            ),
            {
                "game_id": game_id,
                "sport": sport,
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "commence_time": commence_time,
            },
        )
        conn.commit()


def insert_test_odds(
    engine,
    odds_id,
    game_id,
    outcome_name="home",
    price=1.54,
    bookmaker="SBR",
    last_update="2026-02-15 22:30:00",
):
    """Insert test game odds."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            INSERT INTO game_odds (odds_id, game_id, bookmaker, market_name,
                outcome_name, price, last_update)
            VALUES (:odds_id, :game_id, :bookmaker, 'moneyline',
                :outcome_name, :price, :last_update)
        """
            ),
            {
                "odds_id": odds_id,
                "game_id": game_id,
                "bookmaker": bookmaker,
                "outcome_name": outcome_name,
                "price": price,
                "last_update": last_update,
            },
        )
        conn.commit()


# ============================================================
# Tests for compute_real_closing_price
# ============================================================


class TestComputeRealClosingPrice:
    """Test real closing price computation from game_odds."""

    def test_basic_closing_price_home_bet(self):
        """Home bet should get closing price from home outcome odds."""
        engine = _engine()
        create_test_tables(engine)

        # Game: BOS vs LAL on 2026-02-15, market closes at 23:00
        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        # Odds snapshot at 22:30 (30 min before close): home=1.54 → prob=0.649
        insert_test_odds(
            engine,
            "odds1",
            "NBA_20260215_BOS_LAL",
            "home",
            1.54,
            "SBR",
            "2026-02-15 22:30:00",
        )
        insert_test_odds(
            engine,
            "odds2",
            "NBA_20260215_BOS_LAL",
            "away",
            2.85,
            "SBR",
            "2026-02-15 22:30:00",
        )

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_1",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        assert result is not None
        # 1/1.54 = 0.6494 — should be close to this
        assert abs(result - (1.0 / 1.54)) < 0.01

    def test_basic_closing_price_away_bet(self):
        """Away bet should get closing price from away outcome odds."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        insert_test_odds(
            engine,
            "odds1",
            "NBA_20260215_BOS_LAL",
            "home",
            1.54,
            "SBR",
            "2026-02-15 22:30:00",
        )
        insert_test_odds(
            engine,
            "odds2",
            "NBA_20260215_BOS_LAL",
            "away",
            2.85,
            "SBR",
            "2026-02-15 22:30:00",
        )

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_2",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="away",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        assert result is not None
        assert abs(result - (1.0 / 2.85)) < 0.01

    def test_team_abbreviation_bet_on(self):
        """bet_on can be a team abbreviation like 'BOS' instead of 'home'."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        insert_test_odds(
            engine,
            "odds1",
            "NBA_20260215_BOS_LAL",
            "home",
            1.54,
            "SBR",
            "2026-02-15 22:30:00",
        )
        insert_test_odds(
            engine,
            "odds2",
            "NBA_20260215_BOS_LAL",
            "away",
            2.85,
            "SBR",
            "2026-02-15 22:30:00",
        )

        from clv_tracker import compute_real_closing_price

        # bet_on="BOS" should resolve to "home" since BOS is the home team
        result = compute_real_closing_price(
            bet_id="test_bet_3",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="BOS",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        assert result is not None
        assert abs(result - (1.0 / 1.54)) < 0.01

    def test_no_game_odds_snapshot(self):
        """Return None when no game_odds snapshot exists for the game."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        # No game_odds rows inserted

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_4",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        assert result is None

    def test_no_unified_game_match(self):
        """Return None when no unified_games record matches."""
        engine = _engine()
        create_test_tables(engine)
        # No unified_games or game_odds inserted

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_5",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        assert result is None

    def test_stale_snapshot_returns_value_but_flags(self):
        """Snapshot >4hr before market close should still return a value.
        The staleness check is handled at the backfill level, not here."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        # Snapshot at 14:00, market closes at 23:00 — 9 hours gap (stale)
        insert_test_odds(
            engine,
            "odds1",
            "NBA_20260215_BOS_LAL",
            "home",
            1.80,
            "SBR",
            "2026-02-15 14:00:00",
        )

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_6",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        # Should still return a value — staleness is flagged at a higher level
        assert result is not None
        assert abs(result - (1.0 / 1.80)) < 0.01

    def test_uses_latest_snapshot_before_close(self):
        """When multiple snapshots exist, use the one closest to (but before) market close."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        # Early snapshot: home=2.00 (50% prob)
        insert_test_odds(
            engine,
            "odds_early",
            "NBA_20260215_BOS_LAL",
            "home",
            2.00,
            "SBR",
            "2026-02-15 18:00:00",
        )
        # Late snapshot: home=1.54 (65% prob) — this should be used
        insert_test_odds(
            engine,
            "odds_late",
            "NBA_20260215_BOS_LAL",
            "home",
            1.54,
            "SBR",
            "2026-02-15 22:30:00",
        )

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_7",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        # Should use late snapshot (1.54), not early (2.00)
        assert abs(result - (1.0 / 1.54)) < 0.01

    def test_ignores_snapshot_after_market_close(self):
        """Snapshots after market_close_time should be ignored."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        # Before close: home=2.00
        insert_test_odds(
            engine,
            "odds_before",
            "NBA_20260215_BOS_LAL",
            "home",
            2.00,
            "SBR",
            "2026-02-15 22:00:00",
        )
        # After close: home=1.01 (post-result, should be ignored)
        insert_test_odds(
            engine,
            "odds_after",
            "NBA_20260215_BOS_LAL",
            "home",
            1.01,
            "SBR",
            "2026-02-16 02:00:00",
        )

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_8",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        # Should use before-close snapshot (2.00), not after (1.01)
        assert abs(result - (1.0 / 2.00)) < 0.01

    def test_null_last_update_treated_as_pre_close(self):
        """When game_odds.last_update is NULL, treat as available (many SBR rows lack timestamps)."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        # Odds with NULL last_update
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO game_odds (odds_id, game_id, bookmaker, market_name, outcome_name, price, last_update)
                VALUES ('odds_null', 'NBA_20260215_BOS_LAL', 'SBR', 'moneyline', 'home', 1.67, NULL)
            """
                )
            )
            conn.commit()

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_9",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        # NULL timestamp odds should still be usable
        assert result is not None
        assert abs(result - (1.0 / 1.67)) < 0.01

    def test_bookmaker_priority_kalshi_over_sbr(self):
        """When multiple bookmakers have odds, prefer Kalshi over SBR."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_game(
            engine, "NBA_20260215_BOS_LAL", "nba", "2026-02-15", "BOS", "LAL"
        )
        # SBR odds: home=2.00 (50%)
        insert_test_odds(
            engine,
            "odds_sbr",
            "NBA_20260215_BOS_LAL",
            "home",
            2.00,
            "SBR",
            "2026-02-15 22:30:00",
        )
        # Kalshi odds: home=1.54 (65%)
        insert_test_odds(
            engine,
            "odds_kalshi",
            "NBA_20260215_BOS_LAL",
            "home",
            1.54,
            "Kalshi",
            "2026-02-15 22:30:00",
        )

        from clv_tracker import compute_real_closing_price

        result = compute_real_closing_price(
            bet_id="test_bet_10",
            sport="NBA",
            home_team="BOS",
            away_team="LAL",
            bet_on="home",
            placed_date="2026-02-15",
            market_close_time_utc=datetime(2026, 2, 15, 23, 0, 0),
        )

        # Should prefer Kalshi (1.54) over SBR (2.00)
        assert abs(result - (1.0 / 1.54)) < 0.01


# ============================================================
# Tests for backfill_real_clv
# ============================================================


class TestBackfillRealCLV:
    """Test backfilling historical bets with real closing prices."""

    def test_backfill_updates_binary_clv(self):
        """Bets with binary CLV (1.0 or 0.0) should be updated."""
        engine = _engine()
        create_test_tables(engine)

        # Bet with binary CLV (the bug)
        insert_test_bet(
            engine, "bet_1", closing_line_prob=1.0, clv=-0.35, bet_line_prob=0.65
        )
        insert_test_game(engine, "NBA_20260215_BOS_LAL")
        insert_test_odds(
            engine,
            "odds1",
            "NBA_20260215_BOS_LAL",
            "home",
            1.54,
            "SBR",
            "2026-02-15 22:30:00",
        )

        from clv_tracker import backfill_real_clv

        result = backfill_real_clv()

        assert result["updated"] >= 1
        # Verify the bet was updated
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT closing_line_prob, clv FROM placed_bets WHERE bet_id = 'bet_1'"
                )
            ).fetchone()
            # closing_line_prob should no longer be 1.0
            assert row[0] != 1.0
            # CLV should be recalculated: bet_line_prob - closing_line_prob
            expected_clv = 0.65 - (1.0 / 1.54)
            assert abs(row[1] - expected_clv) < 0.01

    def test_backfill_null_when_no_odds(self):
        """Bets with no matching game_odds should get NULL closing price."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_bet(
            engine,
            "bet_no_odds",
            sport="NHL",
            home_team="PIT",
            away_team="CHI",
            closing_line_prob=1.0,
            placed_date="2026-02-20",
            market_close_time="2026-02-20 23:00:00",
        )
        # No game or odds data for this bet

        from clv_tracker import backfill_real_clv

        result = backfill_real_clv()

        assert result["null_count"] >= 1

    def test_backfill_stale_detection(self):
        """Count bets where the last odds snapshot is >4hr before close."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_bet(
            engine,
            "bet_stale",
            closing_line_prob=0.0,
            clv=0.65,
            market_close_time="2026-02-15 23:00:00",
        )
        insert_test_game(engine, "NBA_20260215_BOS_LAL")
        # Snapshot 8 hours before close
        insert_test_odds(
            engine,
            "odds_stale",
            "NBA_20260215_BOS_LAL",
            "home",
            1.80,
            "SBR",
            "2026-02-15 15:00:00",
        )

        from clv_tracker import backfill_real_clv

        result = backfill_real_clv()

        assert result["stale_count"] >= 1

    def test_backfill_skips_non_binary_clv(self):
        """Bets that already have real CLV (not 0.0 or 1.0) should be skipped."""
        engine = _engine()
        create_test_tables(engine)

        # Bet with real CLV (not binary)
        insert_test_bet(engine, "bet_real", closing_line_prob=0.62, clv=0.03)

        from clv_tracker import backfill_real_clv

        result = backfill_real_clv()

        # Should not update this bet
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT closing_line_prob FROM placed_bets WHERE bet_id = 'bet_real'"
                )
            ).fetchone()
            assert row[0] == 0.62  # unchanged

    def test_backfill_returns_counts(self):
        """Backfill should return detailed counts."""
        engine = _engine()
        create_test_tables(engine)

        from clv_tracker import backfill_real_clv

        result = backfill_real_clv()

        assert "updated" in result
        assert "null_count" in result
        assert "stale_count" in result
        assert isinstance(result["updated"], int)


# ============================================================
# Tests for update_real_closing_lines (hourly DAG function)
# ============================================================


class TestUpdateRealClosingLines:
    """Test the hourly CLV update function for the DAG."""

    def test_updates_recently_settled_bets(self):
        """Should update CLV for recently settled bets with binary closing prices."""
        engine = _engine()
        create_test_tables(engine)

        insert_test_bet(
            engine,
            "recent_bet",
            closing_line_prob=1.0,
            clv=-0.35,
            status="won",
            bet_line_prob=0.65,
        )
        insert_test_game(engine, "NBA_20260215_BOS_LAL")
        insert_test_odds(
            engine,
            "odds1",
            "NBA_20260215_BOS_LAL",
            "home",
            1.54,
            "SBR",
            "2026-02-15 22:30:00",
        )

        from clv_tracker import update_real_closing_lines

        count = update_real_closing_lines()

        assert count >= 1

    def test_returns_zero_when_nothing_to_update(self):
        """Should return 0 when no bets need updating."""
        engine = _engine()
        create_test_tables(engine)

        from clv_tracker import update_real_closing_lines

        count = update_real_closing_lines()

        assert count == 0
