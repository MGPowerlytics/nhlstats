from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
from sqlalchemy import create_engine, event, text

from plugins.db_manager import DBManager
from plugins.db_loader import NHLDatabaseLoader
from plugins.kalshi_markets import save_to_db


def _sqlite_db(tmp_path) -> DBManager:
    db_file = tmp_path / "mlb_unified_sync_hotfix.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    @event.listens_for(db.engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return db


def _create_mlb_sync_tables(db: DBManager) -> None:
    with db.engine.begin() as conn:
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
                CREATE TABLE IF NOT EXISTS mlb_games (
                    game_id INTEGER PRIMARY KEY,
                    game_date DATE,
                    season INTEGER,
                    game_type VARCHAR,
                    home_team VARCHAR,
                    away_team VARCHAR,
                    home_score INTEGER,
                    away_score INTEGER,
                    status VARCHAR
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
                    is_pregame BOOLEAN DEFAULT TRUE,
                    external_id VARCHAR,
                    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS team_game_stats (
                    game_id VARCHAR NOT NULL,
                    sport VARCHAR NOT NULL,
                    team VARCHAR NOT NULL,
                    opponent VARCHAR NOT NULL,
                    is_home BOOLEAN NOT NULL,
                    game_date DATE NOT NULL,
                    season VARCHAR NOT NULL,
                    points_for INTEGER,
                    points_against INTEGER,
                    won BOOLEAN,
                    off_rating REAL,
                    def_rating REAL,
                    pace REAL,
                    margin INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (game_id, team),
                    FOREIGN KEY (game_id) REFERENCES unified_games(game_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mlb_team_game_stats_ext (
                    game_id VARCHAR NOT NULL,
                    team VARCHAR NOT NULL,
                    hits INTEGER,
                    errors INTEGER,
                    lob INTEGER,
                    doubles INTEGER,
                    triples INTEGER,
                    home_runs INTEGER,
                    rbi INTEGER,
                    stolen_bases INTEGER,
                    strikeouts INTEGER,
                    walks INTEGER,
                    at_bats INTEGER,
                    obp REAL,
                    slg REAL,
                    ops REAL,
                    woba REAL,
                    era REAL,
                    PRIMARY KEY (game_id, team),
                    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
                )
                """
            )
        )


def _seed_mlb_identity_rows(db: DBManager, synthetic_game_id: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO mlb_games (
                    game_id, game_date, season, game_type, home_team, away_team, status
                ) VALUES (745431, '2024-04-05', 2024, 'R', 'New York Yankees', 'Boston Red Sox', 'Preview')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO unified_games (
                    game_id, sport, game_date, home_team_name, away_team_name, status
                ) VALUES
                    (:synthetic_game_id, 'MLB', '2024-04-05', 'New York Yankees', 'Boston Red Sox', 'pending'),
                    ('745431', 'MLB', '2024-04-05', 'New York Yankees', 'Boston Red Sox', 'scheduled')
                """
            ),
            {"synthetic_game_id": synthetic_game_id},
        )


def _seed_custom_mlb_identity_rows(
    db: DBManager,
    *,
    native_game_id: int,
    game_date: str,
    home_team: str,
    away_team: str,
    synthetic_game_id: str,
) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO mlb_games (
                    game_id, game_date, season, game_type, home_team, away_team, status
                ) VALUES (
                    :native_game_id, :game_date, 2024, 'R', :home_team, :away_team, 'Preview'
                )
                """
            ),
            {
                "native_game_id": native_game_id,
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO unified_games (
                    game_id, sport, game_date, home_team_name, away_team_name, status
                ) VALUES
                    (:synthetic_game_id, 'MLB', :game_date, :home_team, :away_team, 'pending'),
                    (:native_game_id, 'MLB', :game_date, :home_team, :away_team, 'scheduled')
                """
            ),
            {
                "synthetic_game_id": synthetic_game_id,
                "native_game_id": str(native_game_id),
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
            },
        )


def _fetch_game_odds_rows(db: DBManager) -> list[tuple]:
    with db.engine.connect() as conn:
        return conn.execute(
            text(
                """
                SELECT odds_id, game_id, outcome_name, external_id
                FROM game_odds
                ORDER BY odds_id
                """
            )
        ).fetchall()


def _fetch_bookmaker_odds_rows(db: DBManager, bookmaker: str) -> list[tuple]:
    with db.engine.connect() as conn:
        return conn.execute(
            text(
                """
                SELECT odds_id, game_id, bookmaker, market_name, outcome_name, price
                FROM game_odds
                WHERE bookmaker = :bookmaker
                ORDER BY odds_id
                """
            ),
            {"bookmaker": bookmaker},
        ).fetchall()


def _seed_mlb_dependent_rows(db: DBManager, synthetic_game_id: str, ticker: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO game_odds (
                    odds_id, game_id, bookmaker, market_name, outcome_name, price, external_id
                ) VALUES (
                    :odds_id, :game_id, 'Kalshi', 'moneyline', 'home', 1.6, :ticker
                )
                """
            ),
            {
                "odds_id": f"{synthetic_game_id}_kalshi_home",
                "game_id": synthetic_game_id,
                "ticker": ticker,
            },
        )
        team_rows = [
            {
                "game_id": synthetic_game_id,
                "sport": "MLB",
                "team": "New York Yankees",
                "opponent": "Boston Red Sox",
                "is_home": True,
                "game_date": "2024-04-05",
                "season": "2024",
                "points_for": 5,
                "points_against": 3,
                "won": True,
                "margin": 2,
            },
            {
                "game_id": synthetic_game_id,
                "sport": "MLB",
                "team": "Boston Red Sox",
                "opponent": "New York Yankees",
                "is_home": False,
                "game_date": "2024-04-05",
                "season": "2024",
                "points_for": 3,
                "points_against": 5,
                "won": False,
                "margin": -2,
            },
        ]
        for row in team_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO team_game_stats (
                        game_id, sport, team, opponent, is_home, game_date, season,
                        points_for, points_against, won, margin
                    ) VALUES (
                        :game_id, :sport, :team, :opponent, :is_home, :game_date, :season,
                        :points_for, :points_against, :won, :margin
                    )
                    """
                ),
                row,
            )
            conn.execute(
                text(
                    """
                    INSERT INTO mlb_team_game_stats_ext (
                        game_id, team, hits, errors, lob, doubles, home_runs, rbi,
                        strikeouts, walks, at_bats, obp, slg, ops, era
                    ) VALUES (
                        :game_id, :team, 8, 0, 6, 2, 1, :points_for,
                        9, 3, 34, 0.341, 0.447, 0.788, 3.50
                    )
                    """
                ),
                row,
            )


def _fetch_team_stats_ids(db: DBManager) -> list[tuple]:
    with db.engine.connect() as conn:
        return conn.execute(
            text(
                """
                SELECT game_id, team
                FROM team_game_stats
                ORDER BY team
                """
            )
        ).fetchall()


def _fetch_mlb_ext_ids(db: DBManager) -> list[tuple]:
    with db.engine.connect() as conn:
        return conn.execute(
            text(
                """
                SELECT game_id, team
                FROM mlb_team_game_stats_ext
                ORDER BY team
                """
            )
        ).fetchall()


def test_load_mlb_schedule_upserts_unified_games_with_native_gamepk(tmp_path) -> None:
    db = MagicMock()
    loader = NHLDatabaseLoader(db=db)
    schedule_path = tmp_path / "mlb_schedule.json"
    schedule_path.write_text(
        json.dumps(
            {
                "dates": [
                    {
                        "games": [
                            {
                                "gamePk": 745431,
                                "officialDate": "2024-04-05",
                                "season": "2024",
                                "gameType": "R",
                                "teams": {
                                    "home": {
                                        "team": {"name": "New York Yankees", "id": 147},
                                        "score": 5,
                                    },
                                    "away": {
                                        "team": {"name": "Boston Red Sox", "id": 111},
                                        "score": 3,
                                    },
                                },
                                "status": {"abstractGameState": "Final"},
                                "gameDate": "2024-04-05T23:05:00Z",
                                "venue": {"name": "Yankee Stadium"},
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    loader._load_mlb_schedule(schedule_path)

    unified_calls = [
        call for call in db.execute.call_args_list if "INSERT INTO unified_games" in call.args[0]
    ]
    assert len(unified_calls) == 1

    params = unified_calls[0].args[1]
    assert str(params["game_id"]) == "745431"
    assert params["sport"] == "MLB"
    assert params["home_team_name"] == "New York Yankees"
    assert params["away_team_name"] == "Boston Red Sox"
    assert params["status"] == "Final"
    assert params["commence_time"] == "2024-04-05T23:05:00Z"


def test_save_to_db_prefers_native_mlb_game_id_when_synthetic_and_native_rows_coexist(
    tmp_path,
) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    synthetic_game_id = "MLB_20240405_NEWYORKYANKEES_BOSTONREDSOX"
    _seed_mlb_identity_rows(db, synthetic_game_id)

    market = {
        "ticker": "KXMLBGAME-24APR05BOSNYY-NYY",
        "title": "Boston Red Sox at New York Yankees",
        "yes_ask": 56,
    }

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        saved = save_to_db("mlb", [market], db_manager=db)

    assert saved == 1
    with db.engine.connect() as conn:
        unified_ids = conn.execute(
            text("SELECT game_id FROM unified_games WHERE sport = 'MLB' ORDER BY game_id")
        ).fetchall()

    assert [row[0] for row in unified_ids] == ["745431"]
    assert _fetch_game_odds_rows(db) == [
        (
            "745431_kalshi_home",
            "745431",
            "home",
            "KXMLBGAME-24APR05BOSNYY-NYY",
        )
    ]


def test_save_to_db_persists_five_character_mlb_payload_to_native_game_id(tmp_path) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    synthetic_game_id = "MLB_20240421_ARIZONADIAMONDBACKS_CHICAGOWHITESOX"
    _seed_custom_mlb_identity_rows(
        db,
        native_game_id=745999,
        game_date="2024-04-21",
        home_team="Arizona Diamondbacks",
        away_team="Chicago White Sox",
        synthetic_game_id=synthetic_game_id,
    )

    market = {
        "ticker": "KXMLBGAME-24APR21CWSAZ-CWS",
        "title": "Chicago White Sox at Arizona Diamondbacks",
        "yes_ask": 56,
    }

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        saved = save_to_db("mlb", [market], db_manager=db)

    assert saved == 1
    assert _fetch_game_odds_rows(db) == [
        (
            "745999_kalshi_away",
            "745999",
            "away",
            "KXMLBGAME-24APR21CWSAZ-CWS",
        )
    ]


def test_save_to_db_persists_live_abbreviated_mlb_titles_to_native_game_ids(
    tmp_path,
) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    market_specs = [
        {
            "native_game_id": 826001,
            "game_date": "2026-04-22",
            "home_team": "Tampa Bay Rays",
            "away_team": "Cincinnati Reds",
            "ticker": "KXMLBGAME-26APR221310CINTB-TB",
            "title": "Cincinnati vs Tampa Bay Winner?",
        },
        {
            "native_game_id": 826002,
            "game_date": "2026-04-22",
            "home_team": "San Francisco Giants",
            "away_team": "Los Angeles Dodgers",
            "ticker": "KXMLBGAME-26APR222145LADSF-SF",
            "title": "Los Angeles D vs San Francisco Winner?",
        },
        {
            "native_game_id": 826003,
            "game_date": "2026-04-22",
            "home_team": "Kansas City Royals",
            "away_team": "Baltimore Orioles",
            "ticker": "KXMLBGAME-26APR221410BALKC-KC",
            "title": "Baltimore vs Kansas City Winner?",
        },
        {
            "native_game_id": 826004,
            "game_date": "2026-04-22",
            "home_team": "Colorado Rockies",
            "away_team": "San Diego Padres",
            "ticker": "KXMLBGAME-26APR222040SDCOL-SD",
            "title": "San Diego vs Colorado Winner?",
        },
        {
            "native_game_id": 826005,
            "game_date": "2026-04-22",
            "home_team": "Arizona Diamondbacks",
            "away_team": "Chicago White Sox",
            "ticker": "KXMLBGAME-26APR222140CWSAZ-AZ",
            "title": "Chicago WS vs Arizona Winner?",
        },
    ]

    for spec in market_specs:
        _seed_custom_mlb_identity_rows(
            db,
            native_game_id=spec["native_game_id"],
            game_date=spec["game_date"],
            home_team=spec["home_team"],
            away_team=spec["away_team"],
            synthetic_game_id=(
                f"MLB_{spec['game_date'].replace('-', '')}_"
                f"{spec['home_team'].upper().replace(' ', '')}_"
                f"{spec['away_team'].upper().replace(' ', '')}"
            ),
        )

    markets = [
        {"ticker": spec["ticker"], "title": spec["title"], "yes_ask": 56}
        for spec in market_specs
    ]

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        saved = save_to_db("mlb", markets, db_manager=db)

    assert saved == 5
    rows = _fetch_game_odds_rows(db)
    # Verify each row has the correct game_id and ticker.
    # The outcome_name (home/away) depends on ticker suffix matching
    # against abbreviated Kalshi title parsing, so we only check
    # game_id and ticker here.
    native_ids = {str(spec["native_game_id"]) for spec in market_specs}
    tickers = {spec["ticker"] for spec in market_specs}
    for row in rows:
        odds_id, game_id, outcome_name, external_id = row
        assert game_id in native_ids
        assert external_id in tickers
        assert odds_id.startswith(game_id)
    assert len(rows) == 5


def test_save_to_db_cleans_up_stale_synthetic_mlb_odds_id_and_is_rerun_idempotent(
    tmp_path,
) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    synthetic_game_id = "MLB_20240405_NEWYORKYANKEES_BOSTONREDSOX"
    _seed_mlb_identity_rows(db, synthetic_game_id)
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO game_odds (
                    odds_id, game_id, bookmaker, market_name, outcome_name, price, external_id
                ) VALUES (
                    :odds_id, '745431', 'Kalshi', 'moneyline', 'home', 1.6, 'stale-ticker'
                )
                """
            ),
            {"odds_id": f"{synthetic_game_id}_kalshi_home"},
        )
        conn.execute(
            text("DELETE FROM unified_games WHERE game_id = '745431'")
        )

    market = {
        "ticker": "KXMLBGAME-24APR05BOSNYY-NYY",
        "title": "Boston Red Sox at New York Yankees",
        "yes_ask": 56,
    }

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        first_saved = save_to_db("mlb", [market], db_manager=db)
        second_saved = save_to_db("mlb", [market], db_manager=db)

    assert first_saved == 1
    assert second_saved == 1
    assert _fetch_game_odds_rows(db) == [
        (
            "745431_kalshi_home",
            "745431",
            "home",
            "KXMLBGAME-24APR05BOSNYY-NYY",
        )
    ]
    with db.engine.connect() as conn:
        synthetic_rows = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM game_odds
                WHERE odds_id = :synthetic_odds_id
                """
            ),
            {"synthetic_odds_id": f"{synthetic_game_id}_kalshi_home"},
        ).scalar()

    assert synthetic_rows == 0


def test_save_to_db_rewrites_synthetic_bookmaker_odds_ids_to_native_mlb_game_id(
    tmp_path,
) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    synthetic_game_id = "MLB_20240405_NEWYORKYANKEES_BOSTONREDSOX"
    _seed_mlb_identity_rows(db, synthetic_game_id)
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO game_odds (
                    odds_id, game_id, bookmaker, market_name, outcome_name, price
                ) VALUES (
                    :odds_id, :game_id, 'DraftKings', 'h2h', 'home', 2.1
                )
                """
            ),
            {
                "odds_id": f"{synthetic_game_id}_DraftKings_h2h_home",
                "game_id": synthetic_game_id,
            },
        )

    market = {
        "ticker": "KXMLBGAME-24APR05BOSNYY-NYY",
        "title": "Boston Red Sox at New York Yankees",
        "yes_ask": 56,
    }

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        first_saved = save_to_db("mlb", [market], db_manager=db)
        second_saved = save_to_db("mlb", [market], db_manager=db)

    assert first_saved == 1
    assert second_saved == 1
    assert _fetch_bookmaker_odds_rows(db, "DraftKings") == [
        ("745431_DraftKings_h2h_home", "745431", "DraftKings", "h2h", "home", 2.1)
    ]


def test_save_to_db_dedupes_synthetic_bookmaker_odds_when_native_row_already_exists(
    tmp_path,
) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    synthetic_game_id = "MLB_20240405_NEWYORKYANKEES_BOSTONREDSOX"
    _seed_mlb_identity_rows(db, synthetic_game_id)
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO game_odds (
                    odds_id, game_id, bookmaker, market_name, outcome_name, price
                ) VALUES (
                    :odds_id, :game_id, 'DraftKings', 'h2h', 'home', :price
                )
                """
            ),
            {
                "odds_id": f"{synthetic_game_id}_DraftKings_h2h_home",
                "game_id": synthetic_game_id,
                "price": 2.1,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO game_odds (
                    odds_id, game_id, bookmaker, market_name, outcome_name, price
                ) VALUES (
                    '745431_DraftKings_h2h_home', '745431', 'DraftKings', 'h2h', 'home', 1.95
                )
                """
            )
        )

    market = {
        "ticker": "KXMLBGAME-24APR05BOSNYY-NYY",
        "title": "Boston Red Sox at New York Yankees",
        "yes_ask": 56,
    }

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        first_saved = save_to_db("mlb", [market], db_manager=db)
        second_saved = save_to_db("mlb", [market], db_manager=db)

    assert first_saved == 1
    assert second_saved == 1
    assert _fetch_bookmaker_odds_rows(db, "DraftKings") == [
        ("745431_DraftKings_h2h_home", "745431", "DraftKings", "h2h", "home", 1.95)
    ]


def test_save_to_db_transactionally_migrates_mlb_stats_dependencies_before_deleting_synthetic_game(
    tmp_path,
) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    synthetic_game_id = "MLB_20240405_NEWYORKYANKEES_BOSTONREDSOX"
    ticker = "KXMLBGAME-24APR05BOSNYY-NYY"
    _seed_mlb_identity_rows(db, synthetic_game_id)
    _seed_mlb_dependent_rows(db, synthetic_game_id, ticker)

    market = {
        "ticker": ticker,
        "title": "Boston Red Sox at New York Yankees",
        "yes_ask": 56,
    }

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        first_saved = save_to_db("mlb", [market], db_manager=db)
        second_saved = save_to_db("mlb", [market], db_manager=db)

    assert first_saved == 1
    assert second_saved == 1
    with db.engine.connect() as conn:
        unified_ids = conn.execute(
            text("SELECT game_id FROM unified_games WHERE sport = 'MLB' ORDER BY game_id")
        ).fetchall()
        synthetic_unified_rows = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM unified_games
                WHERE game_id = :synthetic_game_id
                """
            ),
            {"synthetic_game_id": synthetic_game_id},
        ).scalar()

    assert [row[0] for row in unified_ids] == ["745431"]
    assert synthetic_unified_rows == 0
    assert _fetch_game_odds_rows(db) == [
        (
            "745431_kalshi_home",
            "745431",
            "home",
            ticker,
        )
    ]
    assert _fetch_team_stats_ids(db) == [
        ("745431", "Boston Red Sox"),
        ("745431", "New York Yankees"),
    ]
    assert _fetch_mlb_ext_ids(db) == [
        ("745431", "Boston Red Sox"),
        ("745431", "New York Yankees"),
    ]


def test_save_to_db_backfills_native_unified_row_before_migrating_mlb_dependencies(
    tmp_path,
) -> None:
    db = _sqlite_db(tmp_path)
    _create_mlb_sync_tables(db)
    synthetic_game_id = "MLB_20240405_NEWYORKYANKEES_BOSTONREDSOX"
    ticker = "KXMLBGAME-24APR05BOSNYY-NYY"
    _seed_mlb_identity_rows(db, synthetic_game_id)
    _seed_mlb_dependent_rows(db, synthetic_game_id, ticker)
    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM unified_games WHERE game_id = '745431'"))

    market = {
        "ticker": ticker,
        "title": "Boston Red Sox at New York Yankees",
        "yes_ask": 56,
    }

    with patch(
        "plugins.database_schema_manager.DatabaseSchemaManager.initialize_schema",
        autospec=True,
    ):
        saved = save_to_db("mlb", [market], db_manager=db)

    assert saved == 1
    with db.engine.connect() as conn:
        unified_ids = conn.execute(
            text("SELECT game_id FROM unified_games WHERE sport = 'MLB' ORDER BY game_id")
        ).fetchall()

    assert [row[0] for row in unified_ids] == ["745431"]
    assert _fetch_game_odds_rows(db) == [
        (
            "745431_kalshi_home",
            "745431",
            "home",
            ticker,
        )
    ]
    assert _fetch_team_stats_ids(db) == [
        ("745431", "Boston Red Sox"),
        ("745431", "New York Yankees"),
    ]
    assert _fetch_mlb_ext_ids(db) == [
        ("745431", "Boston Red Sox"),
        ("745431", "New York Yankees"),
    ]


def test_query_games_for_date_uses_mlb_native_game_ids() -> None:
    from dags import historical_stats_daily as dag_module

    fake_db = MagicMock()
    fake_db.fetch_df.return_value = pd.DataFrame([{"game_id": 745431}])

    with patch("plugins.db_manager.DBManager", return_value=fake_db):
        game_ids = dag_module._query_games_for_date("MLB", date(2024, 4, 5))

    fake_db.fetch_df.assert_called_once()
    query = fake_db.fetch_df.call_args.args[0]
    assert "FROM mlb_games" in query
    assert game_ids == ["745431"]
