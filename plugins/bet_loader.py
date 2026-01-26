"""
Load bet recommendations into PostgreSQL for historical analysis.
"""

import json
from pathlib import Path
from typing import Optional
from db_manager import DBManager, default_db


class BetLoader:
    """Loads bet recommendations into PostgreSQL."""

    def __init__(
        self, db_path: Optional[str] = None, db_manager: DBManager = default_db
    ):
        # Store db_path for tests
        self.db_path = Path(db_path) if db_path else Path("data/nhlstats.duckdb")
        self.db = db_manager
        self._ensure_table()

    def _ensure_table(self):
        """Create bet_recommendations table if it doesn't exist."""
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS bet_recommendations (
                bet_id VARCHAR PRIMARY KEY,
                sport VARCHAR NOT NULL,
                recommendation_date DATE NOT NULL,
                home_team VARCHAR NOT NULL,
                away_team VARCHAR NOT NULL,
                bet_on VARCHAR NOT NULL,
                elo_prob DOUBLE PRECISION NOT NULL,
                market_prob DOUBLE PRECISION NOT NULL,
                edge DOUBLE PRECISION NOT NULL,
                confidence VARCHAR NOT NULL,
                yes_ask INTEGER,
                no_ask INTEGER,
                ticker VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bet_recs_date_sport
            ON bet_recommendations(recommendation_date, sport)
            """
        )

    def load_bets_for_date(self, sport: str, date_str: str) -> int:
        """
        Load bets from JSON file into PostgreSQL.
        """
        bets_file = Path(f"data/{sport}/bets_{date_str}.json")

        if not bets_file.exists():
            print(f"⚠️  No bets file found for {sport} on {date_str}")
            return 0

        with open(bets_file, "r") as f:
            bets = json.load(f)

        if not bets:
            print(f"ℹ️  No bets to load for {sport} on {date_str}")
            return 0

        loaded = 0
        for i, bet in enumerate(bets):
            home_team = bet.get("home_team", bet.get("player", "Unknown"))
            away_team = bet.get("away_team", bet.get("opponent", "Unknown"))
            bet_id = f"{sport}_{date_str}_{i}_{home_team}_{away_team}"

            params = {
                "bet_id": bet_id,
                "sport": sport,
                "date_str": date_str,
                "home_team": home_team,
                "away_team": away_team,
                "bet_on": bet["bet_on"],
                "elo_prob": bet["elo_prob"],
                "market_prob": bet["market_prob"],
                "edge": bet["edge"],
                "confidence": bet["confidence"],
                "yes_ask": bet.get("yes_ask"),
                "no_ask": bet.get("no_ask"),
                "ticker": bet.get("ticker"),
            }

            # Allow DB exceptions to bubble up (fail loud)
            self.db.execute(
                """
                INSERT INTO bet_recommendations
                (bet_id, sport, recommendation_date, home_team, away_team,
                 bet_on, elo_prob, market_prob, edge, confidence,
                 yes_ask, no_ask, ticker)
                VALUES (:bet_id, :sport, :date_str, :home_team, :away_team,
                       :bet_on, :elo_prob, :market_prob, :edge, :confidence,
                       :yes_ask, :no_ask, :ticker)
                ON CONFLICT (bet_id) DO UPDATE SET
                    elo_prob = EXCLUDED.elo_prob,
                    market_prob = EXCLUDED.market_prob,
                    edge = EXCLUDED.edge,
                    confidence = EXCLUDED.confidence
                """,
                params,
            )
            loaded += 1

        print(f"✓ Loaded {loaded} {sport.upper()} bets for {date_str}")
        return loaded

    def get_bets_summary(self, start_date=None, end_date=None):
        """Get summary of bet recommendations by sport and date."""
        query = """
            SELECT
                sport,
                recommendation_date,
                COUNT(*) as num_bets,
                AVG(edge) as avg_edge,
                AVG(elo_prob) as avg_elo_prob,
                SUM(CASE WHEN confidence = 'HIGH' THEN 1 ELSE 0 END) as high_confidence_bets
            FROM bet_recommendations
        """

        params = {}
        if start_date or end_date:
            query += " WHERE 1=1"
            if start_date:
                query += " AND recommendation_date >= :start_date"
                params["start_date"] = start_date
            if end_date:
                query += " AND recommendation_date <= :end_date"
                params["end_date"] = end_date

        query += " GROUP BY sport, recommendation_date ORDER BY recommendation_date DESC, sport"
        return self.db.fetch_df(query, params).values.tolist()


if __name__ == "__main__":
    # Test loading today's bets
    from datetime import date

    loader = BetLoader()
    today = date.today().strftime("%Y-%m-%d")

    print(f"Loading bets for {today}...")
    total = 0
    for sport in ["nba", "nhl", "mlb", "nfl", "epl", "ncaab", "tennis"]:
        count = loader.load_bets_for_date(sport, today)
        total += count

    print(f"\n✓ Total bets loaded: {total}")

    print("\n📊 Recent bets summary:")
    summary = loader.get_bets_summary()
    for row in summary[:20]:
        print(
            f"  {row[0]:6} {row[1]}: {row[2]:2} bets, avg edge: {row[3]:.1%}, avg prob: {row[4]:.1%}, {row[5]} high conf"
        )
