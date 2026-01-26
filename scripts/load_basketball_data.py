import pandas as pd
from sqlalchemy import text
from plugins.db_manager import DBManager
from plugins.ncaab_games import NCAABGames
from plugins.wncaab_games import WNCAABGames


def setup_tables(db):
    print("Initializing Basketball Tables...")

    # NCAAB (Drop and Recreate to ensure schema)
    db.execute("DROP TABLE IF EXISTS ncaab_games CASCADE")
    db.execute("""
        CREATE TABLE ncaab_games (
            game_id VARCHAR PRIMARY KEY,
            game_date DATE,
            season INTEGER,
            home_team VARCHAR,
            away_team VARCHAR,
            home_score INTEGER,
            away_score INTEGER,
            is_neutral BOOLEAN
        )
    """)

    # WNCAAB (Drop and Recreate)
    db.execute("DROP TABLE IF EXISTS wncaab_games CASCADE")
    db.execute("""
        CREATE TABLE wncaab_games (
            game_id VARCHAR PRIMARY KEY,
            game_date DATE,
            season INTEGER,
            home_team VARCHAR,
            away_team VARCHAR,
            home_score INTEGER,
            away_score INTEGER,
            is_neutral BOOLEAN
        )
    """)

    # Unified Games (Ensure exists)
    db.execute("""
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
    """)


def load_ncaab(db, target_date=None):
    print("\n--- Loading NCAAB Data ---")
    ncaab = NCAABGames()
    df = ncaab.load_games()

    if df.empty:
        print("No NCAAB games found.")
        return

    # Filter for target date if needed (or just load everything for 2026)
    # Better to load everything to be safe
    df_2026 = df[df["season"] == 2026]
    print(f"Found {len(df_2026)} NCAAB games for 2026 season.")

    if target_date:
        target_dt = pd.to_datetime(target_date)
        df_target = df[df["date"] == target_dt]
        print(f"Found {len(df_target)} games for {target_date}.")

    count = 0
    with db.get_engine().connect() as conn:
        trans = conn.begin()
        try:
            for _, row in df_2026.iterrows():
                try:
                    game_date = row["date"].strftime("%Y-%m-%d")
                    h_slug = "".join(x for x in str(row["home_team"]) if x.isalnum())
                    a_slug = "".join(x for x in str(row["away_team"]) if x.isalnum())
                    game_id = f"NCAAB_{game_date}_{h_slug}_{a_slug}"

                    params = {
                        "game_id": game_id,
                        "game_date": game_date,
                        "season": int(row["season"]),
                        "home_team": row["home_team"],
                        "away_team": row["away_team"],
                        "home_score": int(row["home_score"]),
                        "away_score": int(row["away_score"]),
                        "is_neutral": bool(row["neutral"]),
                    }

                    conn.execute(
                        text("""
                        INSERT INTO ncaab_games (
                            game_id, game_date, season, home_team, away_team,
                            home_score, away_score, is_neutral
                        ) VALUES (:game_id, :game_date, :season, :home_team, :away_team, :home_score, :away_score, :is_neutral)
                        ON CONFLICT (game_id) DO UPDATE SET
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score
                    """),
                        params,
                    )

                    # Also unified_games
                    conn.execute(
                        text("""
                        INSERT INTO unified_games (
                            game_id, sport, game_date, season, home_team_id, home_team_name,
                            away_team_id, away_team_name, home_score, away_score, status
                        ) VALUES (:game_id, 'NCAAB', :game_date, :season, :home_team, :home_team,
                                  :away_team, :away_team, :home_score, :away_score, 'Scheduled')
                        ON CONFLICT (game_id) DO UPDATE SET
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score
                    """),
                        params,
                    )

                    count += 1
                except Exception as e:
                    print(f"Insert Error: {e}")
                    pass
            trans.commit()
            print(f"✓ Loaded {count} NCAAB games into DB.")
        except Exception as e:
            trans.rollback()
            print(f"Error executing NCAAB transaction: {e}")


def load_wncaab(db, target_date=None):
    print("\n--- Loading WNCAAB Data ---")
    wncaab = WNCAABGames()
    df = wncaab.load_games()

    if df.empty:
        print("No WNCAAB games found.")
        return

    df_2026 = df[df["season"] == 2026]
    print(f"Found {len(df_2026)} WNCAAB games for 2026 season.")

    if target_date:
        target_dt = pd.to_datetime(target_date)
        df_target = df[df["date"] == target_dt]
        print(f"Found {len(df_target)} games for {target_date}.")

    count = 0
    with db.get_engine().connect() as conn:
        trans = conn.begin()
        try:
            for _, row in df_2026.iterrows():
                try:
                    game_date = row["date"].strftime("%Y-%m-%d")
                    h_slug = "".join(x for x in str(row["home_team"]) if x.isalnum())
                    a_slug = "".join(x for x in str(row["away_team"]) if x.isalnum())
                    game_id = f"WNCAAB_{game_date}_{h_slug}_{a_slug}"

                    params = {
                        "game_id": game_id,
                        "game_date": game_date,
                        "season": int(row["season"]),
                        "home_team": row["home_team"],
                        "away_team": row["away_team"],
                        "home_score": int(row["home_score"]),
                        "away_score": int(row["away_score"]),
                        "is_neutral": bool(row["neutral"]),
                    }

                    conn.execute(
                        text("""
                        INSERT INTO wncaab_games (
                            game_id, game_date, season, home_team, away_team,
                            home_score, away_score, is_neutral
                        ) VALUES (:game_id, :game_date, :season, :home_team, :away_team, :home_score, :away_score, :is_neutral)
                        ON CONFLICT (game_id) DO UPDATE SET
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score
                    """),
                        params,
                    )

                    # Also unified_games
                    conn.execute(
                        text("""
                        INSERT INTO unified_games (
                            game_id, sport, game_date, season, home_team_id, home_team_name,
                            away_team_id, away_team_name, home_score, away_score, status
                        ) VALUES (:game_id, 'WNCAAB', :game_date, :season, :home_team, :home_team,
                                  :away_team, :away_team, :home_score, :away_score, 'Scheduled')
                        ON CONFLICT (game_id) DO UPDATE SET
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score
                    """),
                        params,
                    )

                    count += 1
                except Exception as e:
                    print(f"Insert Error: {e}")
                    pass
            trans.commit()
            print(f"✓ Loaded {count} WNCAAB games into DB.")
        except Exception as e:
            trans.rollback()
            print(f"Error executing WNCAAB transaction: {e}")


if __name__ == "__main__":
    db = DBManager()
    setup_tables(db)
    target_date = "2026-01-22"
    load_ncaab(db, target_date)
    load_wncaab(db, target_date)
