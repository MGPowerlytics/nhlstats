"""Tests for Kalshi-specific closing line tracking (TODO-008).

Tests for:
- fetch_and_store_kalshi_closing_prices(): fetches Kalshi prices near market close
  and stores them in game_odds with bookmaker='Kalshi_close'.
- update_real_closing_lines(prefer_kalshi_close=True): prefers Kalshi_close records.
- DAG task capture_kalshi_closing_prices: error-safe wrapper in bet_sync_hourly.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy import text

from db_manager import default_db


# ---------------------------------------------------------------------------
# Helpers reused from test_clv_tracker_fix.py pattern
# ---------------------------------------------------------------------------


def _engine():
    """Get the test engine from the patched default_db."""
    return default_db.engine


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


def insert_bet(
    engine,
    bet_id,
    ticker="KXNBAGAME-26MAR22MINBOS-MIN",
    sport="NBA",
    placed_date="2026-03-22",
    home_team="BOS",
    away_team="MIN",
    bet_on="home",
    side="yes",
    market_close_time=None,
    status="pending",
    bet_line_prob=0.60,
    closing_line_prob=None,
    clv=None,
):
    """Insert a test placed_bet."""
    if market_close_time is None:
        market_close_time = datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            INSERT INTO placed_bets (bet_id, ticker, sport, placed_date, home_team,
                away_team, bet_on, side, market_close_time_utc, status,
                bet_line_prob, closing_line_prob, clv, price_cents, cost_dollars, contracts)
            VALUES (:bet_id, :ticker, :sport, :placed_date, :home_team,
                :away_team, :bet_on, :side, :market_close_time, :status,
                :bet_line_prob, :closing_line_prob, :clv, 60, 6.0, 1)
        """
            ),
            {
                "bet_id": bet_id,
                "ticker": ticker,
                "sport": sport,
                "placed_date": placed_date,
                "home_team": home_team,
                "away_team": away_team,
                "bet_on": bet_on,
                "side": side,
                "market_close_time": market_close_time,
                "status": status,
                "bet_line_prob": bet_line_prob,
                "closing_line_prob": closing_line_prob,
                "clv": clv,
            },
        )
        conn.commit()


def insert_game(
    engine,
    game_id,
    sport="nba",
    game_date="2026-03-22",
    home_team="BOS",
    away_team="MIN",
):
    """Insert a test unified_game."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            INSERT INTO unified_games (game_id, sport, game_date, home_team_name,
                away_team_name, status)
            VALUES (:game_id, :sport, :game_date, :home_team, :away_team, 'scheduled')
        """
            ),
            {
                "game_id": game_id,
                "sport": sport,
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
            },
        )
        conn.commit()


def insert_odds(
    engine,
    odds_id,
    game_id,
    bookmaker="SBR",
    outcome_name="home",
    price=1.70,
    last_update=None,
):
    """Insert a test game_odds row."""
    if last_update is None:
        last_update = datetime.utcnow().isoformat()
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


def _fake_market_data(yes_ask=60, no_ask=40):
    """Return fake Kalshi market data dict (prices in cents)."""
    return {"yes_ask": yes_ask, "no_ask": no_ask, "status": "active"}


# ---------------------------------------------------------------------------
# Tests for fetch_and_store_kalshi_closing_prices()
# ---------------------------------------------------------------------------


class TestFetchAndStoreKalshiClosingPrices:
    """Tests for fetch_and_store_kalshi_closing_prices()."""

    def test_returns_zero_counts_when_no_bets_near_close(self):
        """Returns all-zero counts when no bets are within the lookahead window."""
        engine = _engine()
        create_test_tables(engine)

        # Insert a bet whose close is 2 hours in the future (outside 30-min window)
        far_future = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        insert_bet(engine, "bet_far", market_close_time=far_future)

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch("plugins.kalshi_markets.KalshiAPI") as mock_api_cls:
            mock_creds.return_value = ("fake_key", "fake_pem")
            mock_api_cls.return_value = MagicMock()

            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        assert result == {"fetched": 0, "stored": 0, "errors": 0}

    def test_fetches_price_for_bet_near_close(self):
        """Fetches Kalshi price for a bet whose market closes within lookahead."""
        engine = _engine()
        create_test_tables(engine)

        # Close time within window (15 min from now)
        near_close = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        insert_bet(
            engine,
            "bet_near",
            ticker="KXNBAGAME-26MAR22BOSMIN-BOS",
            sport="NBA",
            placed_date="2026-03-22",
            home_team="BOS",
            away_team="MIN",
            market_close_time=near_close,
        )
        insert_game(engine, "NBA_20260322_BOS_MIN")

        mock_api = MagicMock()
        mock_api.get_market.return_value = _fake_market_data(yes_ask=60, no_ask=40)

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch(
            "plugins.kalshi_markets.KalshiAPI", return_value=mock_api
        ):
            mock_creds.return_value = ("fake_key", "fake_pem")
            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        assert result["fetched"] >= 1
        mock_api.get_market.assert_called_once_with("KXNBAGAME-26MAR22BOSMIN-BOS")

    def test_stores_closing_price_in_game_odds(self):
        """Stores the fetched Kalshi price in game_odds with bookmaker='Kalshi_close'."""
        engine = _engine()
        create_test_tables(engine)

        near_close = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        insert_bet(
            engine,
            "bet_store",
            ticker="KXNBAGAME-26MAR22BOSMIN-BOS",
            sport="NBA",
            placed_date="2026-03-22",
            home_team="BOS",
            away_team="MIN",
            bet_on="home",
            side="yes",
            market_close_time=near_close,
        )
        insert_game(engine, "NBA_20260322_BOS_MIN")

        # yes_ask=60 → home prob=0.60 → decimal odds=1/0.60≈1.667
        mock_api = MagicMock()
        mock_api.get_market.return_value = _fake_market_data(yes_ask=60, no_ask=40)

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch(
            "plugins.kalshi_markets.KalshiAPI", return_value=mock_api
        ):
            mock_creds.return_value = ("fake_key", "fake_pem")
            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        assert result["stored"] >= 1

        # Verify the row is in game_odds with bookmaker='Kalshi_close'
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT bookmaker, outcome_name, price FROM game_odds "
                    "WHERE game_id='NBA_20260322_BOS_MIN' AND bookmaker='Kalshi_close'"
                )
            ).fetchall()

        assert len(rows) >= 1
        bookmakers = {r[0] for r in rows}
        assert "Kalshi_close" in bookmakers

    def test_stored_home_price_matches_yes_ask(self):
        """When bet_on='home' and side='yes', home decimal odds = 1/(yes_ask/100)."""
        engine = _engine()
        create_test_tables(engine)

        near_close = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        insert_bet(
            engine,
            "bet_price",
            ticker="KXNBAGAME-26MAR22BOSMIN-BOS",
            sport="NBA",
            placed_date="2026-03-22",
            home_team="BOS",
            away_team="MIN",
            bet_on="home",
            side="yes",
            market_close_time=near_close,
        )
        insert_game(engine, "NBA_20260322_BOS_MIN")

        # yes_ask=65 → prob=0.65 → decimal odds≈1.538
        mock_api = MagicMock()
        mock_api.get_market.return_value = _fake_market_data(yes_ask=65, no_ask=35)

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch(
            "plugins.kalshi_markets.KalshiAPI", return_value=mock_api
        ):
            mock_creds.return_value = ("fake_key", "fake_pem")
            fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT price FROM game_odds "
                    "WHERE game_id='NBA_20260322_BOS_MIN' "
                    "AND bookmaker='Kalshi_close' AND outcome_name='home'"
                )
            ).fetchone()

        assert row is not None
        expected_decimal_odds = 1.0 / 0.65
        assert abs(row[0] - expected_decimal_odds) < 0.01

    def test_handles_api_initialization_failure_gracefully(self):
        """Returns error count when Kalshi API cannot be initialized."""
        engine = _engine()
        create_test_tables(engine)

        near_close = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        insert_bet(engine, "bet_api_fail", market_close_time=near_close)

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials",
            side_effect=FileNotFoundError("no credentials"),
        ):
            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        assert result["fetched"] == 0
        assert result["stored"] == 0
        # errors not necessarily incremented for init failure — just zero activity

    def test_handles_api_market_fetch_failure_gracefully(self):
        """Increments errors count when get_market() raises an exception."""
        engine = _engine()
        create_test_tables(engine)

        near_close = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        insert_bet(
            engine,
            "bet_mkt_fail",
            ticker="KXNBAGAME-FAIL",
            sport="NBA",
            placed_date="2026-03-22",
            home_team="BOS",
            away_team="MIN",
            market_close_time=near_close,
        )
        insert_game(engine, "NBA_20260322_BOS_MIN")

        mock_api = MagicMock()
        mock_api.get_market.side_effect = Exception("API unavailable")

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch(
            "plugins.kalshi_markets.KalshiAPI", return_value=mock_api
        ):
            mock_creds.return_value = ("fake_key", "fake_pem")
            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        assert result["errors"] >= 1
        assert result["stored"] == 0

    def test_handles_bet_with_no_ticker_gracefully(self):
        """Bets without a ticker are skipped without incrementing errors."""
        engine = _engine()
        create_test_tables(engine)

        near_close = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        # Insert bet with no ticker
        insert_bet(
            engine,
            "bet_no_ticker",
            ticker=None,
            market_close_time=near_close,
        )

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        mock_api = MagicMock()

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch(
            "plugins.kalshi_markets.KalshiAPI", return_value=mock_api
        ):
            mock_creds.return_value = ("fake_key", "fake_pem")
            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        # No ticker = query filters it out; no fetch, no error
        assert result["fetched"] == 0
        mock_api.get_market.assert_not_called()

    def test_handles_missing_game_id_gracefully(self):
        """Bet whose game can't be found in unified_games increments errors."""
        engine = _engine()
        create_test_tables(engine)

        near_close = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        insert_bet(
            engine,
            "bet_no_game",
            ticker="KXNBAGAME-NOTFOUND",
            sport="NBA",
            placed_date="2026-03-22",
            home_team="UNKNOWN_HOME",
            away_team="UNKNOWN_AWAY",
            market_close_time=near_close,
        )
        # No game inserted in unified_games

        mock_api = MagicMock()
        mock_api.get_market.return_value = _fake_market_data()

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch(
            "plugins.kalshi_markets.KalshiAPI", return_value=mock_api
        ):
            mock_creds.return_value = ("fake_key", "fake_pem")
            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        assert result["stored"] == 0
        assert result["errors"] >= 1

    def test_bet_just_past_close_also_captured(self):
        """A bet whose close time is within lookahead_minutes in the PAST is included."""
        engine = _engine()
        create_test_tables(engine)

        # 15 minutes ago = within window
        recent_past = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        insert_bet(
            engine,
            "bet_past",
            ticker="KXNBAGAME-26MAR22BOSMIN-BOS",
            sport="NBA",
            placed_date="2026-03-22",
            home_team="BOS",
            away_team="MIN",
            market_close_time=recent_past,
        )
        insert_game(engine, "NBA_20260322_BOS_MIN")

        mock_api = MagicMock()
        mock_api.get_market.return_value = _fake_market_data(yes_ask=55, no_ask=45)

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials"
        ) as mock_creds, patch(
            "plugins.kalshi_markets.KalshiAPI", return_value=mock_api
        ):
            mock_creds.return_value = ("fake_key", "fake_pem")
            result = fetch_and_store_kalshi_closing_prices(lookahead_minutes=30)

        assert result["fetched"] >= 1

    def test_returns_dict_with_correct_keys(self):
        """Return value always has 'fetched', 'stored', 'errors' keys."""
        engine = _engine()
        create_test_tables(engine)

        from clv_tracker import fetch_and_store_kalshi_closing_prices

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials",
            side_effect=FileNotFoundError("no creds"),
        ):
            result = fetch_and_store_kalshi_closing_prices()

        assert set(result.keys()) == {"fetched", "stored", "errors"}


# ---------------------------------------------------------------------------
# Tests for update_real_closing_lines(prefer_kalshi_close=True)
# ---------------------------------------------------------------------------


class TestUpdateRealClosingLinesPreferKalshiClose:
    """Tests that update_real_closing_lines prefers Kalshi_close records."""

    def test_prefers_kalshi_close_over_sbr(self):
        """When Kalshi_close and SBR records exist, Kalshi_close price is used."""
        engine = _engine()
        create_test_tables(engine)

        insert_game(
            engine, "NBA_20260322_BOS_MIN", sport="nba",
            game_date="2026-03-22", home_team="BOS", away_team="MIN"
        )

        close_time = "2026-03-22 23:00:00"

        # SBR closing price: 1.70 → 1/1.70 ≈ 0.588 prob
        insert_odds(
            engine, "sbr_home", "NBA_20260322_BOS_MIN",
            bookmaker="SBR", outcome_name="home",
            price=1.70, last_update="2026-03-22 22:45:00"
        )
        # Kalshi_close price: 1.54 → 1/1.54 ≈ 0.649 prob
        insert_odds(
            engine, "kalshi_home", "NBA_20260322_BOS_MIN",
            bookmaker="Kalshi_close", outcome_name="home",
            price=1.54, last_update="2026-03-22 22:50:00"
        )

        # Bet with binary closing_line_prob
        insert_bet(
            engine, "bet_prefer_kc",
            ticker="KXNBAGAME-26MAR22BOSMIN-BOS",
            sport="NBA", placed_date="2026-03-22",
            home_team="BOS", away_team="MIN",
            bet_on="home", side="yes",
            market_close_time=close_time,
            status="won",
            bet_line_prob=0.70,
            closing_line_prob=1.0,  # binary = needs update
            clv=None,
        )

        from clv_tracker import update_real_closing_lines

        count = update_real_closing_lines(prefer_kalshi_close=True)

        assert count >= 1

        # Closing prob should now reflect Kalshi_close price (≈ 1/1.54 ≈ 0.649)
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT closing_line_prob FROM placed_bets WHERE bet_id='bet_prefer_kc'"
                )
            ).fetchone()

        assert row is not None
        # Should be closer to 1/1.54 ≈ 0.649 (Kalshi_close) than 1/1.70 ≈ 0.588 (SBR)
        expected_kalshi_close_prob = 1.0 / 1.54
        expected_sbr_prob = 1.0 / 1.70
        assert abs(row[0] - expected_kalshi_close_prob) < abs(
            row[0] - expected_sbr_prob
        ), (
            f"Expected Kalshi_close prob ({expected_kalshi_close_prob:.3f}) "
            f"to be preferred over SBR prob ({expected_sbr_prob:.3f}), "
            f"got {row[0]:.3f}"
        )

    def test_falls_back_to_sbr_when_no_kalshi_close(self):
        """Falls back to SBR when no Kalshi_close record exists."""
        engine = _engine()
        create_test_tables(engine)

        insert_game(
            engine, "NBA_20260322_BOS_MIN", sport="nba",
            game_date="2026-03-22", home_team="BOS", away_team="MIN"
        )

        close_time = "2026-03-22 23:00:00"
        insert_odds(
            engine, "sbr_home2", "NBA_20260322_BOS_MIN",
            bookmaker="SBR", outcome_name="home",
            price=1.80, last_update="2026-03-22 22:45:00"
        )
        # No Kalshi_close record

        insert_bet(
            engine, "bet_fallback",
            ticker="KXNBAGAME-26MAR22BOSMIN-BOS",
            sport="NBA", placed_date="2026-03-22",
            home_team="BOS", away_team="MIN",
            bet_on="home", side="yes",
            market_close_time=close_time,
            status="won",
            bet_line_prob=0.65,
            closing_line_prob=1.0,
            clv=None,
        )

        from clv_tracker import update_real_closing_lines

        count = update_real_closing_lines(prefer_kalshi_close=True)

        assert count >= 1

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT closing_line_prob FROM placed_bets WHERE bet_id='bet_fallback'"
                )
            ).fetchone()

        assert row is not None
        # Should use SBR price: 1/1.80 ≈ 0.556
        expected_sbr_prob = 1.0 / 1.80
        assert abs(row[0] - expected_sbr_prob) < 0.01

    def test_prefer_kalshi_close_false_ignores_kalshi_close(self):
        """When prefer_kalshi_close=False, Kalshi_close gets normal bookmaker priority."""
        engine = _engine()
        create_test_tables(engine)

        insert_game(
            engine, "NBA_20260322_BOS_MIN", sport="nba",
            game_date="2026-03-22", home_team="BOS", away_team="MIN"
        )

        close_time = "2026-03-22 23:00:00"
        # Kalshi (not Kalshi_close) has highest priority normally
        insert_odds(
            engine, "kalshi_normal", "NBA_20260322_BOS_MIN",
            bookmaker="Kalshi", outcome_name="home",
            price=1.60, last_update="2026-03-22 22:55:00"
        )
        insert_odds(
            engine, "kalshi_close_ign", "NBA_20260322_BOS_MIN",
            bookmaker="Kalshi_close", outcome_name="home",
            price=1.50, last_update="2026-03-22 22:50:00"
        )

        insert_bet(
            engine, "bet_no_pref",
            sport="NBA", placed_date="2026-03-22",
            home_team="BOS", away_team="MIN",
            bet_on="home", side="yes",
            market_close_time=close_time,
            status="won",
            bet_line_prob=0.70,
            closing_line_prob=1.0,
            clv=None,
        )

        from clv_tracker import update_real_closing_lines

        update_real_closing_lines(prefer_kalshi_close=False)

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT closing_line_prob FROM placed_bets WHERE bet_id='bet_no_pref'"
                )
            ).fetchone()

        # Either Kalshi or Kalshi_close, just verify a real price was used (not 1.0)
        assert row is not None
        assert row[0] is not None
        assert row[0] != 1.0


# ---------------------------------------------------------------------------
# Tests for constants
# ---------------------------------------------------------------------------


class TestKalshiClosingConstants:
    """Tests that required constants exist and are correct."""

    def test_kalshi_closing_bookmaker_constant_exists(self):
        """KALSHI_CLOSING_BOOKMAKER constant should be 'Kalshi_close'."""
        from plugins.constants import KALSHI_CLOSING_BOOKMAKER

        assert KALSHI_CLOSING_BOOKMAKER == "Kalshi_close"

    def test_kalshi_closing_window_minutes_constant_exists(self):
        """KALSHI_CLOSING_WINDOW_MINUTES should be 30."""
        from plugins.constants import KALSHI_CLOSING_WINDOW_MINUTES

        assert KALSHI_CLOSING_WINDOW_MINUTES == 30


# ---------------------------------------------------------------------------
# Tests for DAG task capture_kalshi_closing_prices
# ---------------------------------------------------------------------------


class TestDagTaskCaptureKalshiClosingPrices:
    """Tests for the capture_kalshi_closing_prices DAG task."""

    def test_dag_has_capture_kalshi_closing_prices_task(self):
        """DAG bet_sync_hourly must contain capture_kalshi_closing_prices task."""
        from airflow.models import DagBag

        dagbag = DagBag(dag_folder="dags/", include_examples=False)
        assert "bet_sync_hourly" in dagbag.dags

        dag = dagbag.dags["bet_sync_hourly"]
        task_ids = [task.task_id for task in dag.tasks]
        assert "capture_kalshi_closing_prices" in task_ids

    def test_capture_task_runs_after_clv_update(self):
        """capture_kalshi_closing_prices must be downstream of update_closing_lines."""
        from airflow.models import DagBag

        dagbag = DagBag(dag_folder="dags/", include_examples=False)
        dag = dagbag.dags["bet_sync_hourly"]

        capture_task = dag.get_task("capture_kalshi_closing_prices")
        upstream_ids = {t.task_id for t in capture_task.upstream_list}
        assert "update_closing_lines" in upstream_ids, (
            f"Expected 'update_closing_lines' in upstream of "
            f"capture_kalshi_closing_prices, got: {upstream_ids}"
        )

    def test_capture_task_callable_does_not_raise_on_api_failure(self):
        """The capture_kalshi_closing_prices callable must not raise even if API fails."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("dags").resolve()))

        from bet_sync_hourly import capture_kalshi_closing_prices_task

        with patch(
            "plugins.kalshi_markets.load_kalshi_credentials",
            side_effect=FileNotFoundError("no credentials"),
        ):
            # Should not raise
            result = capture_kalshi_closing_prices_task()

        # Returns 0 on failure (graceful)
        assert result is not None

    def test_capture_task_calls_fetch_and_store(self):
        """The DAG callable invokes fetch_and_store_kalshi_closing_prices."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("dags").resolve()))

        from bet_sync_hourly import capture_kalshi_closing_prices_task

        with patch(
            "clv_tracker.fetch_and_store_kalshi_closing_prices"
        ) as mock_fetch:
            mock_fetch.return_value = {"fetched": 2, "stored": 4, "errors": 0}
            result = capture_kalshi_closing_prices_task()

        mock_fetch.assert_called_once()
        assert result is not None
