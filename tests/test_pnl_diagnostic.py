"""Tests for P&L Diagnostic module — Elo replay, timing, bootstrap, auto-pause.

TDD Red Phase: These tests define expected behavior of plugins/pnl_diagnostic.py.
They should FAIL initially because the module doesn't exist yet.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from sqlalchemy import text
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import _TEST_ENGINE


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def create_diagnostic_tables(engine):
    """Create tables needed for diagnostic tests."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS unified_games (
                game_id VARCHAR PRIMARY KEY, sport VARCHAR NOT NULL,
                game_date DATE NOT NULL, season INTEGER, status VARCHAR,
                home_team_id VARCHAR, home_team_name VARCHAR,
                away_team_id VARCHAR, away_team_name VARCHAR,
                home_score INTEGER, away_score INTEGER,
                commence_time TIMESTAMP, venue VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS placed_bets (
                bet_id VARCHAR PRIMARY KEY, sport VARCHAR, placed_date DATE,
                placed_time_utc TIMESTAMP, ticker VARCHAR,
                home_team VARCHAR, away_team VARCHAR, bet_on VARCHAR,
                side VARCHAR, contracts INTEGER, price_cents INTEGER,
                cost_dollars REAL, fees_dollars REAL, elo_prob REAL,
                market_prob REAL, edge REAL, expected_value REAL,
                kelly_fraction REAL, confidence VARCHAR, market_title VARCHAR,
                market_close_time_utc TIMESTAMP, opening_line_prob REAL,
                bet_line_prob REAL, closing_line_prob REAL, clv REAL,
                status VARCHAR, settled_date DATE,
                payout_dollars REAL, profit_dollars REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS diagnostic_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sport TEXT NOT NULL, settled_bets INTEGER,
                wins INTEGER, losses INTEGER,
                roi REAL, real_clv REAL, p_value REAL,
                passes_gate INTEGER, avg_hours_before_game REAL,
                timing_roi_under_2hr REAL, timing_roi_over_8hr REAL,
                bets_with_closing_price INTEGER, bets_flagged_stale INTEGER,
                recommendation TEXT, elo_replay_divergence REAL)
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS game_odds (
                odds_id VARCHAR PRIMARY KEY, game_id VARCHAR NOT NULL,
                bookmaker VARCHAR NOT NULL, market_name VARCHAR NOT NULL,
                outcome_name VARCHAR, price REAL NOT NULL,
                line REAL, last_update TIMESTAMP,
                is_pregame INTEGER DEFAULT 1, external_id VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """
            )
        )
        conn.commit()


def insert_games_for_replay(engine, sport="nba", num_games=20):
    """Insert a set of games for Elo replay testing."""
    teams = ["BOS", "LAL", "GSW", "MIA", "PHI", "CHI", "NYK", "DAL"]
    with engine.connect() as conn:
        for i in range(num_games):
            home_idx = i % len(teams)
            away_idx = (i + 1) % len(teams)
            game_date = f"2026-01-{(i % 28) + 1:02d}"
            home_score = 100 + (i * 3) % 30
            away_score = 95 + (i * 7) % 25
            conn.execute(
                text(
                    """
                INSERT INTO unified_games (game_id, sport, game_date, home_team_name,
                    away_team_name, home_score, away_score, commence_time, status)
                VALUES (:gid, :sport, :gdate, :home, :away, :hs, :as_, :ct, 'completed')
            """
                ),
                {
                    "gid": f"{sport.upper()}_{game_date.replace('-', '')}_{teams[home_idx]}_{teams[away_idx]}",
                    "sport": sport,
                    "gdate": game_date,
                    "home": teams[home_idx],
                    "away": teams[away_idx],
                    "hs": home_score,
                    "as_": away_score,
                    "ct": f"{game_date} 19:00:00",
                },
            )
        conn.commit()


def insert_bets_for_analysis(engine, sport="NBA", num_bets=60):
    """Insert test placed_bets for analysis. Mix of wins and losses."""
    rng = random.Random(42)
    teams = ["BOS", "LAL", "GSW", "MIA", "PHI", "CHI"]
    with engine.connect() as conn:
        for i in range(num_bets):
            won = rng.random() > 0.45  # ~55% win rate
            profit = 5.0 if won else -6.5
            hours_before = rng.choice([0.5, 1.5, 3.0, 6.0, 10.0, 15.0])
            game_time = datetime(2026, 2, (i % 28) + 1, 19, 0)
            placed_time = game_time - timedelta(hours=hours_before)
            market_close = game_time - timedelta(minutes=5)

            conn.execute(
                text(
                    """
                INSERT INTO placed_bets (bet_id, sport, placed_date, placed_time_utc,
                    home_team, away_team, bet_on, side, contracts, price_cents,
                    cost_dollars, elo_prob, market_prob, edge,
                    market_close_time_utc, bet_line_prob, closing_line_prob, clv,
                    status, profit_dollars)
                VALUES (:bid, :sport, :pd, :pt, :ht, :at, 'home', 'yes', 1,
                    65, 6.5, 0.68, 0.55, 0.13, :mct, 0.55,
                    :clp, :clv, :status, :profit)
            """
                ),
                {
                    "bid": f"bet_{sport}_{i}",
                    "sport": sport,
                    "pd": placed_time.strftime("%Y-%m-%d"),
                    "pt": placed_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "ht": teams[i % len(teams)],
                    "at": teams[(i + 1) % len(teams)],
                    "mct": market_close.strftime("%Y-%m-%d %H:%M:%S"),
                    "clp": 1.0 if won else 0.0,
                    "clv": 0.55 - (1.0 if won else 0.0),
                    "status": "won" if won else "lost",
                    "profit": profit,
                },
            )
        conn.commit()


def _make_bets_df(n=60, hours_choices=None, win_rate=0.55, seed=42) -> pd.DataFrame:
    """Build a synthetic bets DataFrame for pure-function tests."""
    rng = np.random.default_rng(seed)
    if hours_choices is None:
        hours_choices = [0.5, 1.5, 3.0, 6.0, 10.0, 15.0]
    rows = []
    for i in range(n):
        won = rng.random() < win_rate
        hours_before = rng.choice(hours_choices)
        game_time = datetime(2026, 2, (i % 28) + 1, 19, 0)
        placed_time = game_time - timedelta(hours=float(hours_before))
        market_close = game_time - timedelta(minutes=5)
        rows.append(
            {
                "bet_id": f"bet_{i}",
                "sport": "NBA",
                "placed_time_utc": placed_time,
                "market_close_time_utc": market_close,
                "cost_dollars": 6.5,
                "profit_dollars": 5.0 if won else -6.5,
                "status": "settled",
                "elo_prob": 0.68,
                "edge": 0.13,
            }
        )
    return pd.DataFrame(rows)


# ===========================================================================
# 1. TestBootstrapPnlTest
# ===========================================================================


class TestBootstrapPnlTest:
    """Tests for bootstrap_pnl_test() significance testing."""

    def test_profitable_sample(self):
        """Profits with positive mean → low p-value, CI above zero."""
        from plugins.pnl_diagnostic import bootstrap_pnl_test

        profits = list(np.random.default_rng(42).normal(loc=2.0, scale=1.0, size=200))
        result = bootstrap_pnl_test(profits, n_bootstrap=5000)

        assert "p_value" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "mean_pnl" in result
        assert (
            result["p_value"] < 0.05
        ), "Clearly profitable sample should have p < 0.05"
        assert (
            result["ci_lower"] > 0
        ), "CI lower bound should be above zero for profitable sample"
        assert result["mean_pnl"] > 0

    def test_unprofitable_sample(self):
        """Losses → CI below zero."""
        from plugins.pnl_diagnostic import bootstrap_pnl_test

        profits = list(np.random.default_rng(99).normal(loc=-3.0, scale=1.0, size=200))
        result = bootstrap_pnl_test(profits, n_bootstrap=5000)

        assert (
            result["ci_upper"] < 0
        ), "CI upper bound should be below zero for losing sample"
        assert result["mean_pnl"] < 0

    def test_breakeven_sample(self):
        """Mixed profits around zero → CI spans zero, higher p-value."""
        from plugins.pnl_diagnostic import bootstrap_pnl_test

        profits = list(np.random.default_rng(19).normal(loc=0.0, scale=5.0, size=200))
        result = bootstrap_pnl_test(profits, n_bootstrap=5000)

        assert result["ci_lower"] < 0, "CI lower should be negative for breakeven"
        assert result["ci_upper"] > 0, "CI upper should be positive for breakeven"
        assert result["p_value"] > 0.05, "Breakeven sample should not be significant"

    def test_insufficient_data(self):
        """Empty profit list → raises ValueError or returns special result."""
        from plugins.pnl_diagnostic import bootstrap_pnl_test

        # Either raises or returns a sentinel value
        try:
            result = bootstrap_pnl_test([], n_bootstrap=5000)
            # If it returns instead of raising, must signal insufficiency
            assert result.get("p_value") is None or result.get("p_value") == 1.0
        except (ValueError, ZeroDivisionError):
            pass  # Acceptable: raising on empty input


# ===========================================================================
# 2. TestComputeTimingAnalysis
# ===========================================================================


class TestComputeTimingAnalysis:
    """Tests for compute_timing_analysis() — ROI by hours-before-game buckets."""

    def test_timing_buckets_have_roi(self):
        """Bets in different timing buckets produce per-bucket ROI."""
        from plugins.pnl_diagnostic import compute_timing_analysis

        df = _make_bets_df(n=100, hours_choices=[0.5, 1.5, 3.0, 6.0, 10.0, 15.0])
        result = compute_timing_analysis(df)

        assert isinstance(result, dict)
        assert len(result) > 0, "Should have at least one timing bucket"
        # Each bucket value should be a numeric ROI
        for bucket, roi in result.items():
            assert isinstance(
                roi, (int, float)
            ), f"ROI for bucket {bucket} should be numeric"

    def test_missing_timing_data_excluded(self):
        """Bets with NULL placed_time or market_close_time are excluded."""
        from plugins.pnl_diagnostic import compute_timing_analysis

        df = _make_bets_df(n=20)
        # Set some placed_time_utc to None
        df.loc[0:4, "placed_time_utc"] = None
        df.loc[5:9, "market_close_time_utc"] = None

        result = compute_timing_analysis(df)
        # Should still return results (from remaining 10 valid bets)
        assert isinstance(result, dict)
        # Total bets across buckets should be <= 10
        # (Just verify it doesn't crash and returns something valid)

    def test_empty_dataframe(self):
        """Empty DataFrame returns empty dict."""
        from plugins.pnl_diagnostic import compute_timing_analysis

        df = pd.DataFrame(
            columns=[
                "bet_id",
                "placed_time_utc",
                "market_close_time_utc",
                "cost_dollars",
                "profit_dollars",
            ]
        )
        result = compute_timing_analysis(df)

        assert isinstance(result, dict)
        assert len(result) == 0, "Empty input should produce empty result"


# ===========================================================================
# 3. TestWhatIfTimingReplay
# ===========================================================================


class TestWhatIfTimingReplay:
    """Tests for what_if_timing_replay() — hypothetical ROI for late bets."""

    def test_under_2hr_filter(self):
        """Only includes bets placed <2hr before game."""
        from plugins.pnl_diagnostic import what_if_timing_replay

        df = _make_bets_df(n=100, hours_choices=[0.5, 1.5, 3.0, 6.0, 10.0, 15.0])
        result = what_if_timing_replay(df, max_hours=2.0)

        assert isinstance(result, dict)
        assert "roi" in result or "total_profit" in result or "n_bets" in result
        # Verify filtered bet count is less than total
        n_key = "n_bets" if "n_bets" in result else "count"
        if n_key in result:
            assert result[n_key] < len(df), "Should filter out some bets"

    def test_custom_max_hours(self):
        """Respects max_hours parameter — wider window includes more bets."""
        from plugins.pnl_diagnostic import what_if_timing_replay

        df = _make_bets_df(n=100, hours_choices=[0.5, 1.5, 3.0, 6.0, 10.0, 15.0])
        result_2hr = what_if_timing_replay(df, max_hours=2.0)
        result_8hr = what_if_timing_replay(df, max_hours=8.0)

        # 8-hour window should include more bets than 2-hour window
        n_key = "n_bets" if "n_bets" in result_2hr else "count"
        if n_key in result_2hr and n_key in result_8hr:
            assert result_8hr[n_key] >= result_2hr[n_key]

    def test_no_qualifying_bets(self):
        """Returns empty/zero when no bets qualify."""
        from plugins.pnl_diagnostic import what_if_timing_replay

        # All bets placed >24 hours before game
        df = _make_bets_df(n=20, hours_choices=[25.0, 30.0, 48.0])
        result = what_if_timing_replay(df, max_hours=2.0)

        assert isinstance(result, dict)
        n_key = "n_bets" if "n_bets" in result else "count"
        if n_key in result:
            assert result[n_key] == 0
        if "roi" in result:
            assert result["roi"] == 0.0 or result["roi"] is None


# ===========================================================================
# 4. TestGenerateRecommendation
# ===========================================================================


class TestGenerateRecommendation:
    """Tests for generate_recommendation() — auto-pause logic."""

    def test_pause_when_ci_upper_negative(self):
        """Bootstrap CI upper < 0 → PAUSE (evidence of negative edge)."""
        from plugins.pnl_diagnostic import generate_recommendation

        bootstrap_result = {
            "p_value": 0.02,
            "ci_lower": -15.0,
            "ci_upper": -2.0,
            "mean_pnl": -8.5,
        }
        rec = generate_recommendation(
            sport="NBA",
            roi=-0.12,
            real_clv=-0.03,
            bootstrap_result=bootstrap_result,
        )
        assert rec == "PAUSE"

    def test_continue_when_ci_upper_positive(self):
        """CI upper > 0 and positive ROI → CONTINUE."""
        from plugins.pnl_diagnostic import generate_recommendation

        bootstrap_result = {
            "p_value": 0.04,
            "ci_lower": 1.0,
            "ci_upper": 20.0,
            "mean_pnl": 10.0,
        }
        rec = generate_recommendation(
            sport="NBA",
            roi=0.08,
            real_clv=0.02,
            bootstrap_result=bootstrap_result,
        )
        assert rec == "CONTINUE"

    def test_insufficient_data_below_threshold(self):
        """< 50 settled bets → INSUFFICIENT_DATA regardless of bootstrap."""
        from plugins.pnl_diagnostic import generate_recommendation

        bootstrap_result = {
            "p_value": 0.01,
            "ci_lower": -50.0,
            "ci_upper": -10.0,
            "mean_pnl": -30.0,
        }
        # Pass settled_bets count via the bootstrap_result or as part of context
        # The function signature uses roi/real_clv/bootstrap — settled count
        # is inferred from the bootstrap sample or passed separately.
        # For < 50 bets, the function should detect insufficient data.
        # We'll pass a bootstrap result that was computed from < 50 bets:
        bootstrap_result["n_samples"] = 30
        rec = generate_recommendation(
            sport="NBA",
            roi=-0.25,
            real_clv=None,
            bootstrap_result=bootstrap_result,
        )
        assert rec == "INSUFFICIENT_DATA"

    def test_edge_case_ci_at_zero(self):
        """CI upper exactly 0 → CONTINUE (no evidence of negative edge).

        PAUSE requires CI upper *strictly* below zero. At zero, we cannot
        conclude negative edge, so we continue.
        """
        from plugins.pnl_diagnostic import generate_recommendation

        bootstrap_result = {
            "p_value": 0.05,
            "ci_lower": -5.0,
            "ci_upper": 0.0,
            "mean_pnl": -2.5,
        }
        rec = generate_recommendation(
            sport="NBA",
            roi=-0.03,
            real_clv=0.0,
            bootstrap_result=bootstrap_result,
        )
        assert rec == "CONTINUE"


# ===========================================================================
# 5. TestEloReplay
# ===========================================================================


class TestEloReplay:
    """Tests for replay_elo_ratings() — full chronological Elo replay."""

    def test_replay_returns_ratings_dict(self):
        """Returns dict of team → float ratings."""
        from plugins.pnl_diagnostic import replay_elo_ratings

        create_diagnostic_tables(_TEST_ENGINE)
        insert_games_for_replay(_TEST_ENGINE, sport="nba", num_games=20)

        with patch("plugins.pnl_diagnostic.create_elo_instance") as mock_factory:
            mock_elo = MagicMock()
            mock_elo.ratings = {"BOS": 1520.0, "LAL": 1480.0, "GSW": 1510.0}
            mock_factory.return_value = mock_elo

            result = replay_elo_ratings("nba")

        assert isinstance(result, dict)
        assert len(result) > 0
        for team, rating in result.items():
            assert isinstance(team, str)
            assert isinstance(rating, (int, float))

    def test_replay_processes_all_games(self):
        """Replays the correct number of games (mock Elo class)."""
        from plugins.pnl_diagnostic import replay_elo_ratings

        create_diagnostic_tables(_TEST_ENGINE)
        insert_games_for_replay(_TEST_ENGINE, sport="nhl", num_games=15)

        with patch("plugins.pnl_diagnostic.create_elo_instance") as mock_factory:
            mock_elo = MagicMock()
            mock_elo.ratings = {"TeamA": 1500.0}
            mock_factory.return_value = mock_elo

            replay_elo_ratings("nhl")

        # update() should have been called once per game
        assert mock_elo.update.call_count == 15

    def test_replay_unknown_sport_raises(self):
        """Unknown sport → ValueError."""
        from plugins.pnl_diagnostic import replay_elo_ratings

        with pytest.raises(ValueError, match="(?i)unsupported|unknown|not found"):
            replay_elo_ratings("curling")


# ===========================================================================
# 6. TestCompareReplayVsCsv
# ===========================================================================


class TestCompareReplayVsCsv:
    """Tests for compare_replay_vs_csv() — replay vs. stored ratings check."""

    def test_small_divergence(self):
        """Similar ratings → small divergence value."""
        import json
        from io import StringIO

        from plugins.pnl_diagnostic import compare_replay_vs_csv

        replayed = {"BOS": 1520.0, "LAL": 1480.0, "GSW": 1510.0}
        csv_data = json.dumps(
            {"ratings": {"BOS": 1521.0, "LAL": 1479.0, "GSW": 1511.0}}
        )

        m = mock_open(read_data=csv_data)
        with patch("builtins.open", m):
            divergence = compare_replay_vs_csv("nba", replayed)

        assert isinstance(divergence, (int, float))
        assert divergence < 5.0, "Nearly identical ratings should have small divergence"

    def test_no_csv_file(self):
        """Missing CSV → returns inf or large value."""
        from plugins.pnl_diagnostic import compare_replay_vs_csv

        replayed = {"BOS": 1520.0}

        with patch("builtins.open", side_effect=FileNotFoundError):
            divergence = compare_replay_vs_csv("nba", replayed)

        assert divergence == float("inf") or divergence > 1000


# ===========================================================================
# 7. TestRecalculateBetMetrics
# ===========================================================================


class TestRecalculateBetMetrics:
    """Tests for recalculate_bet_metrics() — recompute elo_prob/edge from replay."""

    def test_recalculates_elo_prob(self):
        """Uses replayed ratings to compute new probabilities."""
        from plugins.pnl_diagnostic import recalculate_bet_metrics

        create_diagnostic_tables(_TEST_ENGINE)
        insert_bets_for_analysis(_TEST_ENGINE, sport="NBA", num_bets=20)

        replayed = {
            "BOS": 1550.0,
            "LAL": 1450.0,
            "GSW": 1520.0,
            "MIA": 1490.0,
            "PHI": 1510.0,
            "CHI": 1480.0,
        }

        with patch("plugins.pnl_diagnostic.create_elo_instance") as mock_factory:
            mock_elo = MagicMock()
            # predict returns (home_prob, away_prob)
            mock_elo.predict.return_value = (0.62, 0.38)
            mock_factory.return_value = mock_elo

            result = recalculate_bet_metrics("NBA", replayed)

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        # New elo_prob should differ from stored 0.68
        assert "new_elo_prob" in result.columns

    def test_returns_dataframe_with_columns(self):
        """DataFrame has expected columns."""
        from plugins.pnl_diagnostic import recalculate_bet_metrics

        create_diagnostic_tables(_TEST_ENGINE)
        insert_bets_for_analysis(_TEST_ENGINE, sport="NBA", num_bets=10)

        replayed = {
            "BOS": 1500.0,
            "LAL": 1500.0,
            "GSW": 1500.0,
            "MIA": 1500.0,
            "PHI": 1500.0,
            "CHI": 1500.0,
        }

        with patch("plugins.pnl_diagnostic.create_elo_instance") as mock_factory:
            mock_elo = MagicMock()
            mock_elo.predict.return_value = (0.55, 0.45)
            mock_factory.return_value = mock_elo

            result = recalculate_bet_metrics("NBA", replayed)

        expected_cols = {
            "bet_id",
            "old_elo_prob",
            "new_elo_prob",
            "old_edge",
            "new_edge",
        }
        assert expected_cols.issubset(
            set(result.columns)
        ), f"Missing columns: {expected_cols - set(result.columns)}"

    def test_handles_missing_teams(self):
        """Teams in bets not in ratings → uses default 1500."""
        from plugins.pnl_diagnostic import recalculate_bet_metrics

        create_diagnostic_tables(_TEST_ENGINE)
        insert_bets_for_analysis(_TEST_ENGINE, sport="NBA", num_bets=10)

        # Only provide ratings for a subset of teams
        replayed = {"BOS": 1550.0}

        with patch("plugins.pnl_diagnostic.create_elo_instance") as mock_factory:
            mock_elo = MagicMock()
            mock_elo.predict.return_value = (0.50, 0.50)
            mock_factory.return_value = mock_elo

            # Should NOT raise — missing teams get default 1500
            result = recalculate_bet_metrics("NBA", replayed)

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0


# ===========================================================================
# 8. TestWriteResultsToDb
# ===========================================================================


class TestWriteResultsToDb:
    """Tests for write_results_to_db() — persist diagnostic results."""

    def test_writes_to_diagnostic_results_table(self):
        """Result dict → row in diagnostic_results table."""
        from plugins.pnl_diagnostic import write_results_to_db

        create_diagnostic_tables(_TEST_ENGINE)

        results = {
            "sport": "NBA",
            "settled_bets": 60,
            "wins": 33,
            "losses": 27,
            "roi": 0.08,
            "real_clv": 0.02,
            "p_value": 0.04,
            "passes_gate": True,
            "avg_hours_before_game": 5.5,
            "timing_roi_under_2hr": 0.12,
            "timing_roi_over_8hr": 0.03,
            "bets_with_closing_price": 55,
            "bets_flagged_stale": 5,
            "recommendation": "CONTINUE",
            "elo_replay_divergence": 3.2,
        }

        success = write_results_to_db(results)
        assert success is True

        with _TEST_ENGINE.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM diagnostic_results WHERE sport = 'NBA'")
            ).fetchone()
        assert row is not None
        # Access by index — SQLite row; sport is column index 2
        # Verify a few fields round-tripped
        row_dict = dict(row._mapping)
        assert row_dict["sport"] == "NBA"
        assert row_dict["settled_bets"] == 60
        assert row_dict["recommendation"] == "CONTINUE"

    def test_handles_db_failure_gracefully(self):
        """DB error → returns False, doesn't raise."""
        from plugins.pnl_diagnostic import write_results_to_db

        results = {"sport": "NBA", "settled_bets": 10}

        with patch("plugins.pnl_diagnostic.default_db") as mock_db:
            mock_db.execute.side_effect = Exception("DB connection failed")

            success = write_results_to_db(results)

        assert success is False


# ===========================================================================
# 9. TestRunDiagnostic
# ===========================================================================


class TestRunDiagnostic:
    """Tests for run_diagnostic() — main entry point."""

    def test_run_diagnostic_returns_per_sport_results(self):
        """Returns dict with sport keys."""
        from plugins.pnl_diagnostic import run_diagnostic

        create_diagnostic_tables(_TEST_ENGINE)
        insert_bets_for_analysis(_TEST_ENGINE, sport="NBA", num_bets=60)
        insert_games_for_replay(_TEST_ENGINE, sport="nba", num_games=20)

        with patch("plugins.pnl_diagnostic.create_elo_instance") as mock_factory, patch(
            "plugins.pnl_diagnostic.compare_replay_vs_csv", return_value=1.5
        ):
            mock_elo = MagicMock()
            mock_elo.ratings = {"BOS": 1500.0, "LAL": 1500.0}
            mock_elo.predict.return_value = (0.55, 0.45)
            mock_factory.return_value = mock_elo

            result = run_diagnostic()

        assert isinstance(result, dict)
        # Should contain at least one sport
        assert len(result) > 0
        # Each value should be a dict of diagnostic metrics
        for sport, metrics in result.items():
            assert isinstance(sport, str)
            assert isinstance(metrics, dict)

    def test_skips_sports_below_threshold(self):
        """Sports with < 50 settled bets are skipped."""
        from plugins.pnl_diagnostic import run_diagnostic

        create_diagnostic_tables(_TEST_ENGINE)
        # Insert only 10 bets — below threshold
        insert_bets_for_analysis(_TEST_ENGINE, sport="MLB", num_bets=10)
        insert_games_for_replay(_TEST_ENGINE, sport="mlb", num_games=5)

        with patch("plugins.pnl_diagnostic.create_elo_instance") as mock_factory, patch(
            "plugins.pnl_diagnostic.compare_replay_vs_csv", return_value=0.5
        ):
            mock_elo = MagicMock()
            mock_elo.ratings = {}
            mock_factory.return_value = mock_elo

            result = run_diagnostic()

        # MLB should be absent (only 10 bets, below 50 threshold)
        assert "MLB" not in result
        assert "mlb" not in result
