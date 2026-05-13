"""Contract tests for dashboard source-table seed fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine

from plugins.db_manager import DBManager
from tests.contracts.fixtures.dashboard_seed_samples import (
    DASHBOARD_READ_MODEL_COVERAGE,
    SOURCE_TABLE_KEYS,
    build_dashboard_empty_state_seed_payload,
    build_dashboard_source_seed_payload,
    clear_dashboard_source_rows,
    seed_dashboard_empty_state_source_rows,
    seed_dashboard_source_rows,
)


@pytest.fixture
def dashboard_seed_db() -> Iterator[DBManager]:
    """Create a SQLite stand-in with PostgreSQL-compatible source columns."""

    engine = create_engine("sqlite://", echo=False)
    db = DBManager.__new__(DBManager)
    db.engine = engine
    db.connection_string = "sqlite://"
    _create_source_tables(db)
    yield db
    engine.dispose()


def _create_source_tables(db: DBManager) -> None:
    db.execute(
        """
        CREATE TABLE portfolio_value_snapshots (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY,
            balance_dollars DOUBLE PRECISION,
            portfolio_value_dollars DOUBLE PRECISION,
            cumulative_deposits_dollars DOUBLE PRECISION DEFAULT 0.0,
            drawdown_gate_active BOOLEAN DEFAULT FALSE,
            drawdown_gate_reason_code VARCHAR,
            drawdown_gate_reason_detail VARCHAR,
            created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE unified_games (
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
    db.execute(
        """
        CREATE TABLE game_odds (
            odds_id VARCHAR PRIMARY KEY,
            game_id VARCHAR NOT NULL,
            bookmaker VARCHAR NOT NULL,
            market_name VARCHAR NOT NULL,
            outcome_name VARCHAR,
            price DECIMAL(10, 4) NOT NULL,
            line DECIMAL(10, 4),
            last_update TIMESTAMP,
            is_pregame BOOLEAN DEFAULT TRUE,
            external_id VARCHAR,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE bet_recommendations (
            bet_id VARCHAR PRIMARY KEY,
            sport VARCHAR NOT NULL,
            recommendation_date DATE NOT NULL,
            home_team VARCHAR NOT NULL,
            away_team VARCHAR NOT NULL,
            home_rating DOUBLE PRECISION,
            away_rating DOUBLE PRECISION,
            bet_on VARCHAR NOT NULL,
            elo_prob DOUBLE PRECISION NOT NULL,
            market_prob DOUBLE PRECISION NOT NULL,
            edge DOUBLE PRECISION NOT NULL,
            expected_value DOUBLE PRECISION,
            kelly_fraction DOUBLE PRECISION,
            confidence VARCHAR NOT NULL,
            yes_ask INTEGER,
            no_ask INTEGER,
            ticker VARCHAR,
            quote_price_cents INTEGER,
            quote_price_role VARCHAR,
            quote_source_system VARCHAR,
            quote_bookmaker VARCHAR,
            quote_observed_at TIMESTAMP,
            quote_loaded_at TIMESTAMP,
            quote_payload_ref VARCHAR,
            quote_freshness_result VARCHAR,
            quote_fallback_status VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE placed_bets (
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
            cost_dollars DOUBLE PRECISION,
            fees_dollars DOUBLE PRECISION,
            elo_prob DOUBLE PRECISION,
            market_prob DOUBLE PRECISION,
            edge DOUBLE PRECISION,
            expected_value DOUBLE PRECISION,
            kelly_fraction DOUBLE PRECISION,
            confidence VARCHAR,
            market_title VARCHAR,
            market_close_time_utc TIMESTAMP,
            opening_line_prob DOUBLE PRECISION,
            bet_line_prob DOUBLE PRECISION,
            closing_line_prob DOUBLE PRECISION,
            clv DOUBLE PRECISION,
            status VARCHAR,
            settled_date DATE,
            payout_dollars DOUBLE PRECISION,
            profit_dollars DOUBLE PRECISION,
            source VARCHAR,
            recommendation_id VARCHAR,
            recommendation_canonical_game_id VARCHAR,
            recommendation_market_ticker VARCHAR,
            recommendation_selection_key VARCHAR,
            recommendation_linkage_status VARCHAR,
            recommendation_linkage_basis VARCHAR,
            entry_price_cents INTEGER,
            entry_quote_role VARCHAR,
            entry_price_source VARCHAR,
            entry_quote_source_system VARCHAR,
            entry_quote_bookmaker VARCHAR,
            entry_quote_observed_at TIMESTAMP,
            entry_quote_loaded_at TIMESTAMP,
            entry_quote_payload_ref VARCHAR,
            entry_quote_freshness_result VARCHAR,
            entry_quote_fallback_status VARCHAR,
            close_quote_source VARCHAR,
            close_quote_at TIMESTAMP,
            close_quote_loaded_at TIMESTAMP,
            close_quote_payload_ref VARCHAR,
            close_price_role VARCHAR,
            close_freshness_result VARCHAR,
            selected_close_rule VARCHAR,
            selected_close_provenance VARCHAR,
            close_fallback_status VARCHAR,
            clv_source_type VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE elo_ratings (
            rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport VARCHAR NOT NULL,
            entity_type VARCHAR NOT NULL DEFAULT 'team',
            entity_id VARCHAR NOT NULL,
            entity_name VARCHAR NOT NULL,
            rating DECIMAL(10, 2) NOT NULL,
            valid_from TIMESTAMP NOT NULL,
            valid_to TIMESTAMP,
            games_played INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE UNIQUE INDEX idx_elo_ratings_unique_active
        ON elo_ratings (sport, entity_type, entity_id)
        WHERE valid_to IS NULL
        """
    )
    db.execute(
        """
        CREATE TABLE mlb_model_predictions (
            prediction_id VARCHAR PRIMARY KEY,
            model_version VARCHAR NOT NULL,
            game_id VARCHAR NOT NULL,
            market_name VARCHAR NOT NULL DEFAULT 'moneyline',
            outcome_name VARCHAR NOT NULL,
            run_date DATE NOT NULL,
            model_prob DOUBLE PRECISION NOT NULL,
            market_prob DOUBLE PRECISION,
            edge DOUBLE PRECISION,
            expected_value DOUBLE PRECISION,
            calibration_method VARCHAR,
            ece_at_train DOUBLE PRECISION,
            feature_hash VARCHAR NOT NULL,
            simulation_summary TEXT,
            abstain BOOLEAN NOT NULL DEFAULT FALSE,
            abstention_reason VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE tennis_model_evaluations (
            run_date DATE NOT NULL,
            model_version VARCHAR NOT NULL,
            data_source VARCHAR NOT NULL,
            rows INTEGER NOT NULL,
            holdout_rows INTEGER NOT NULL,
            betmgm_holdout_rows INTEGER,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            beats_betmgm BOOLEAN,
            baseline_log_loss DOUBLE PRECISION,
            ensemble_log_loss DOUBLE PRECISION,
            ensemble_market_log_loss DOUBLE PRECISION,
            betmgm_log_loss DOUBLE PRECISION,
            baseline_brier DOUBLE PRECISION,
            ensemble_brier DOUBLE PRECISION,
            ensemble_market_brier DOUBLE PRECISION,
            betmgm_brier DOUBLE PRECISION,
            baseline_accuracy DOUBLE PRECISION,
            ensemble_accuracy DOUBLE PRECISION,
            ensemble_market_accuracy DOUBLE PRECISION,
            betmgm_accuracy DOUBLE PRECISION,
            baseline_actionable_count INTEGER,
            ensemble_actionable_count INTEGER,
            log_loss_delta DOUBLE PRECISION,
            brier_delta DOUBLE PRECISION,
            accuracy_delta DOUBLE PRECISION,
            ensemble_vs_betmgm_log_loss_delta DOUBLE PRECISION,
            ensemble_vs_betmgm_brier_delta DOUBLE PRECISION,
            ensemble_vs_betmgm_accuracy_delta DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (run_date, model_version, data_source)
        )
        """
    )


def _table_counts(db: DBManager) -> dict[str, int]:
    return {
        table: int(db.fetch_scalar(f"SELECT COUNT(*) FROM {table}"))
        for table in SOURCE_TABLE_KEYS
    }


class TestDashboardSeedFixturePayloads:
    """Unit-level invariants for deterministic source-table fixture rows."""

    def test_source_seed_payload_is_deterministic_and_deep_copied(self) -> None:
        first = build_dashboard_source_seed_payload()
        second = build_dashboard_source_seed_payload()

        assert first == second
        first["placed_bets"][0]["status"] = "lost"
        assert second["placed_bets"][0]["status"] == "open"

    def test_seed_includes_all_required_source_categories(self) -> None:
        payload = build_dashboard_source_seed_payload()

        assert tuple(payload) == SOURCE_TABLE_KEYS
        assert all(payload[table] for table in SOURCE_TABLE_KEYS)

    def test_seed_uses_current_source_columns_not_dashboard_aliases(self) -> None:
        payload = build_dashboard_source_seed_payload()

        assert set(payload["portfolio_value_snapshots"][0]) == {
            "snapshot_hour_utc",
            "balance_dollars",
            "portfolio_value_dollars",
            "cumulative_deposits_dollars",
            "drawdown_gate_active",
            "drawdown_gate_reason_code",
            "drawdown_gate_reason_detail",
            "created_at_utc",
        }
        assert {
            "home_team_name",
            "away_team_name",
            "commence_time",
            "game_date",
        } <= set(payload["unified_games"][0])
        assert {"bookmaker", "market_name", "outcome_name", "price"} <= set(
            payload["game_odds"][0]
        )
        assert {"external_id", "last_update"} <= set(payload["game_odds"][0])
        assert {
            "bet_id",
            "recommendation_date",
            "home_team",
            "away_team",
            "bet_on",
            "elo_prob",
            "market_prob",
            "edge",
            "expected_value",
            "kelly_fraction",
            "confidence",
            "yes_ask",
            "no_ask",
            "ticker",
            "created_at",
        } <= set(payload["bet_recommendations"][0])
        assert {
            "placed_time_utc",
            "cost_dollars",
            "payout_dollars",
            "profit_dollars",
            "status",
        } <= set(payload["placed_bets"][0])
        assert {"entity_id", "entity_name", "rating", "valid_from", "valid_to"} <= set(
            payload["elo_ratings"][0]
        )
        assert {
            "prediction_id",
            "model_version",
            "run_date",
            "model_prob",
            "feature_hash",
        } <= set(payload["mlb_model_predictions"][0])
        assert {
            "run_date",
            "model_version",
            "data_source",
            "rows",
            "ensemble_log_loss",
        } <= set(payload["tennis_model_evaluations"][0])

        stale_dashboard_aliases = {"portfolio_value", "timestamp", "placed_at", "stake"}
        for rows in payload.values():
            for row in rows:
                assert stale_dashboard_aliases.isdisjoint(row)

    def test_source_field_invariants_cover_dashboard_pages(self) -> None:
        payload = build_dashboard_source_seed_payload()

        assert set(DASHBOARD_READ_MODEL_COVERAGE) == {
            "dashboard_portfolio_v1",
            "dashboard_live_markets_v1",
            "dashboard_rankings_v1",
            "dashboard_calibration_v1",
            "dashboard_data_quality_v1",
            "dashboard_bet_detail_v1",
            "dashboard_tennis_predictions_v1",
            "dashboard_tennis_model_health_v1",
            "dashboard_mlb_model_health_v1",
        }
        for source_tables in DASHBOARD_READ_MODEL_COVERAGE.values():
            assert all(payload[table] for table in source_tables)

        statuses = {row["status"] for row in payload["placed_bets"]}
        assert statuses >= {"open", "won"}
        assert all(status == status.lower() for status in statuses)
        assert any(row["settled_date"] for row in payload["placed_bets"])
        assert all(row["valid_to"] is None for row in payload["elo_ratings"])
        assert any(row["sport"] == "TENNIS" for row in payload["bet_recommendations"])
        assert any(
            row["model_version"] == "mlb_moneyline_public_v1"
            for row in payload["mlb_model_predictions"]
        )
        assert all(0 <= row["elo_prob"] <= 1 for row in payload["bet_recommendations"])
        assert all(
            0 <= row["market_prob"] <= 1 for row in payload["bet_recommendations"]
        )

    def test_empty_state_payload_has_zero_rows_for_every_source_table(self) -> None:
        payload = build_dashboard_empty_state_seed_payload()

        assert tuple(payload) == SOURCE_TABLE_KEYS
        assert all(rows == [] for rows in payload.values())


class TestDashboardSeedFixtureDatabaseBehavior:
    """DB-level behavior for idempotent seed/clear utilities."""

    def test_seed_can_run_twice_without_duplicate_logical_rows(
        self, dashboard_seed_db: DBManager
    ) -> None:
        expected = seed_dashboard_source_rows(dashboard_seed_db)
        seed_dashboard_source_rows(dashboard_seed_db)

        assert _table_counts(dashboard_seed_db) == expected

    def test_seed_updates_existing_logical_rows_without_duplication(
        self, dashboard_seed_db: DBManager
    ) -> None:
        seed_dashboard_source_rows(dashboard_seed_db)
        payload = build_dashboard_source_seed_payload(
            portfolio_value_snapshots__0__balance_dollars=1300.75,
            placed_bets__0__status="lost",
            elo_ratings__0__rating=1599.1,
        )
        seed_dashboard_source_rows(dashboard_seed_db, payload)

        assert _table_counts(dashboard_seed_db) == {
            table: len(rows) for table, rows in payload.items()
        }
        assert (
            dashboard_seed_db.fetch_scalar(
                "SELECT balance_dollars FROM portfolio_value_snapshots"
            )
            == 1300.75
        )
        assert (
            dashboard_seed_db.fetch_scalar(
                "SELECT status FROM placed_bets WHERE bet_id = :bet_id",
                {"bet_id": payload["placed_bets"][0]["bet_id"]},
            )
            == "lost"
        )
        assert (
            dashboard_seed_db.fetch_scalar(
                """
                SELECT rating
                FROM elo_ratings
                WHERE entity_id = 'NYR' AND valid_to IS NULL
                """
            )
            == 1599.1
        )

    def test_clear_and_empty_state_seed_do_not_drop_source_tables(
        self, dashboard_seed_db: DBManager
    ) -> None:
        seed_dashboard_source_rows(dashboard_seed_db)

        assert clear_dashboard_source_rows(dashboard_seed_db) == {
            table: 0 for table in SOURCE_TABLE_KEYS
        }
        assert _table_counts(dashboard_seed_db) == {
            table: 0 for table in SOURCE_TABLE_KEYS
        }

        seed_dashboard_source_rows(dashboard_seed_db)
        assert seed_dashboard_empty_state_source_rows(dashboard_seed_db) == {
            table: 0 for table in SOURCE_TABLE_KEYS
        }
        assert _table_counts(dashboard_seed_db) == {
            table: 0 for table in SOURCE_TABLE_KEYS
        }
        table_count = dashboard_seed_db.fetch_scalar(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN (
                'portfolio_value_snapshots',
                'unified_games',
                'game_odds',
                'bet_recommendations',
                'placed_bets',
                'elo_ratings',
                'mlb_model_predictions',
                'tennis_model_evaluations'
              )
            """
        )
        assert table_count == len(SOURCE_TABLE_KEYS)
