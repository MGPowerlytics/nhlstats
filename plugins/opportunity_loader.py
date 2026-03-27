"""Opportunity loader for portfolio optimization.

This module handles loading bet opportunities from various sources
(database, JSON files) and processing them into BetOpportunity objects.

Includes automatic Kalshi ticker resolution: recommendations that lack
a Kalshi ticker are matched against the ``game_odds`` table so they
can be routed to the Kalshi exchange for execution.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


from plugins.portfolio_parsers import DatabaseRowParser, JsonFileParser
from plugins.portfolio_types import BetOpportunity, extract_ticker_date


class OpportunityLoader:
    """Load and process bet opportunities from various sources."""

    def __init__(
        self,
        db_parser: Optional[DatabaseRowParser] = None,
        json_parser: Optional[JsonFileParser] = None,
    ):
        """Initialize opportunity loader with parsers.

        Args:
            db_parser: Parser for database rows (default: DatabaseRowParser())
            json_parser: Parser for JSON data (default: JsonFileParser())
        """
        self._db_parser = db_parser or DatabaseRowParser()
        self._json_parser = json_parser or JsonFileParser()

    def load_from_database(
        self,
        date_str: str,
        sports: Optional[List[str]] = None,
    ) -> List[BetOpportunity]:
        """Load all bet opportunities from PostgreSQL database for a given date.

        Args:
            date_str: Date string in YYYY-MM-DD format
            sports: List of sports to load (default: all major sports)

        Returns:
            List of BetOpportunity objects
        """
        if sports is None:
            sports = [
                "nhl",
                "nba",
                "mlb",
                "nfl",
                "ncaab",
                "tennis",
                "epl",
                "ligue1",
                "wncaab",
                "cba",
                "unrivaled",
            ]

        from plugins.db_manager import default_db

        opportunities = []
        skipped_stale = 0

        sports_list = ", ".join([f"'{sport}'" for sport in sports])
        query = f"""
            SELECT sport, ticker, bet_on, home_team, away_team,
                   home_rating, away_rating, elo_prob, market_prob,
                   edge, confidence, yes_ask, no_ask, bet_id
            FROM bet_recommendations
            WHERE recommendation_date = :rec_date
                AND sport IN ({sports_list})
            ORDER BY sport, home_team, away_team
        """

        try:
            results = default_db.fetch_df(query, {"rec_date": date_str})
            if results.empty:
                print(f"⚠️  No bet recommendations found in database for {date_str}")
                return opportunities

            print(
                f"📊 Loaded {len(results)} bet recommendations from database for {date_str}"
            )

            for _, row in results.iterrows():
                sport = row["sport"]
                ticker = row["ticker"]

                # Skip stale tickers
                ticker_date = extract_ticker_date(ticker)
                if ticker_date and ticker_date < date_str:
                    skipped_stale += 1
                    continue

                opp = self._db_parser.parse(row, sport)
                if opp:
                    opportunities.append(opp)

            # Resolve Kalshi tickers for opportunities that don't have them
            self._resolve_kalshi_tickers(opportunities, date_str, default_db)

            loaded_with_ticker = sum(1 for o in opportunities if o.ticker)
            print(
                f"📊 {loaded_with_ticker}/{len(opportunities)} opportunities have Kalshi tickers"
            )

            # Keep only opportunities with tickers (required for bet placement)
            if loaded_with_ticker < len(opportunities):
                no_ticker = len(opportunities) - loaded_with_ticker
                opportunities = [o for o in opportunities if o.ticker]
                print(f"⚠️  Dropped {no_ticker} opportunities without Kalshi tickers")

        except Exception as e:
            print(f"❌ Error loading opportunities from database: {e}")

        if skipped_stale > 0:
            print(f"⚠️  Skipped {skipped_stale} stale opportunities")

        return opportunities

    @staticmethod
    def _build_game_id(
        sport: str, date_str: str, home_team: str, away_team: str
    ) -> str:
        """Build a game_id matching the format used in game_odds.

        Format: ``SPORT_YYYYMMDD_HOMETEAM_AWAYTEAM`` with team names
        uppercased and spaces/special characters removed.
        """
        date_part = date_str.replace("-", "")
        clean_home = re.sub(r"[^A-Z]", "", home_team.upper())
        clean_away = re.sub(r"[^A-Z]", "", away_team.upper())
        return f"{sport.upper()}_{date_part}_{clean_home}_{clean_away}"

    def _resolve_kalshi_tickers(
        self,
        opportunities: List[BetOpportunity],
        date_str: str,
        db_manager,
    ) -> None:
        """Look up Kalshi tickers from game_odds for opportunities missing them.

        For each opportunity without a ticker, constructs the expected game_id
        and queries the game_odds table for a matching Kalshi entry.

        Args:
            opportunities: List of BetOpportunity objects (mutated in place)
            date_str: Date string in YYYY-MM-DD format
            db_manager: Database manager instance
        """
        needs_ticker = [o for o in opportunities if not o.ticker]
        if not needs_ticker:
            return

        try:
            # Batch-fetch all Kalshi tickers for recent games
            ticker_df = db_manager.fetch_df(
                """
                SELECT game_id, outcome_name, external_id
                FROM game_odds
                WHERE bookmaker = 'Kalshi'
                  AND external_id IS NOT NULL
                  AND external_id != ''
                  AND last_update > :cutoff
                """,
                {"cutoff": f"{date_str} 00:00:00"},
            )
            if ticker_df.empty:
                return

            # Build lookup: (game_id, outcome_name) -> external_id
            ticker_lookup: Dict[Tuple[str, str], str] = {}
            for _, row in ticker_df.iterrows():
                key = (row["game_id"], row["outcome_name"])
                ticker_lookup[key] = row["external_id"]

            resolved = 0
            for opp in needs_ticker:
                game_id = self._build_game_id(
                    opp.sport, date_str, opp.home_team, opp.away_team
                )
                outcome = opp.bet_on  # "home" or "away"
                ticker = ticker_lookup.get((game_id, outcome))
                if ticker:
                    opp.ticker = ticker
                    resolved += 1

            if resolved > 0:
                print(f"🔗 Resolved {resolved} Kalshi tickers from game_odds")

        except Exception as e:
            print(f"⚠️  Ticker resolution failed: {e}")

    def load_from_files(
        self,
        date_str: str,
        sports: Optional[List[str]] = None,
    ) -> List[BetOpportunity]:
        """Load all bet opportunities from JSON files for a given date.

        Args:
            date_str: Date string in YYYY-MM-DD format
            sports: List of sports to load (default: all major sports)

        Returns:
            List of BetOpportunity objects
        """
        if sports is None:
            sports = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"]

        opportunities = []
        total_skipped = 0

        for sport in sports:
            sport_opps, skipped = self._load_sport_opportunities_from_file(
                sport, date_str
            )
            opportunities.extend(sport_opps)
            total_skipped += skipped

        if total_skipped > 0:
            print(f"⚠️  Skipped {total_skipped} stale opportunities from files")

        return opportunities

    def _load_sport_opportunities_from_file(
        self, sport: str, date_str: str
    ) -> Tuple[List[BetOpportunity], int]:
        """Load opportunities from a single sport's JSON file.

        Args:
            sport: Sport name (e.g., 'nhl', 'nba')
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Tuple of (opportunities list, skipped count)
        """
        data_dir = Path("data") / sport
        file_path = data_dir / f"bets_{date_str}.json"

        if not file_path.exists():
            return [], 0

        try:
            with open(file_path, "r") as f:
                bets_data = json.load(f)

            if not isinstance(bets_data, list):
                print(f"⚠️  Invalid data format in {file_path}")
                return [], 0

            return self._process_bets_data(bets_data, sport, date_str)

        except Exception as e:
            print(f"❌ Error loading {sport} opportunities from {file_path}: {e}")
            return [], 0

    def _process_bets_data(
        self, bets_data: List[Dict], sport: str, date_str: str
    ) -> Tuple[List[BetOpportunity], int]:
        """Process a list of bet data entries.

        Args:
            bets_data: List of bet data dictionaries
            sport: Sport name
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Tuple of (opportunities list, skipped count)
        """
        opportunities = []
        skipped = 0

        for bet in bets_data:
            opp, is_stale = self._process_single_bet(bet, sport, date_str)
            if opp:
                opportunities.append(opp)
            elif is_stale:
                skipped += 1

        return opportunities, skipped

    def _process_single_bet(
        self, bet: Dict, sport: str, date_str: str
    ) -> Tuple[Optional[BetOpportunity], bool]:
        """Process a single bet entry, returning opportunity and stale flag.

        Args:
            bet: Bet data dictionary
            sport: Sport name
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Tuple of (BetOpportunity or None, is_stale boolean)
        """
        ticker = bet.get("ticker", "")
        if not ticker:
            return None, False

        # Check if bet is stale
        if self._is_stale_bet(bet, ticker, date_str):
            return None, True

        # Parse the bet
        opp = self._json_parser.parse(bet, sport)
        return opp, False

    def _is_stale_bet(self, bet: Dict, ticker: str, date_str: str) -> bool:
        """Check if a bet is stale based on game date or ticker date.

        Args:
            bet: Bet data dictionary
            ticker: Kalshi ticker string
            date_str: Current date string in YYYY-MM-DD format

        Returns:
            True if bet is stale, False otherwise
        """
        # Check game date from bet data
        game_date = bet.get("game_date")
        if game_date and game_date < date_str:
            return True

        # Check ticker date
        ticker_date = extract_ticker_date(ticker)
        if ticker_date and ticker_date < date_str:
            return True

        return False
