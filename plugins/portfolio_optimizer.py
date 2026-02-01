"""Portfolio-level bet sizing and optimization across all sports.

This module implements:
- Kelly Criterion for optimal bet sizing
- Portfolio-level risk management
- Daily spending limits
- Multi-sport allocation optimization
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import re
from pathlib import Path
import pandas as pd


def extract_game_date(game_id: str) -> Optional[str]:
    """Extract game date from game_id like TENNIS_20260129_ALCARAZ_ZVEREV.

    Returns date in YYYY-MM-DD format or None if not found.
    """
    # Match pattern like SPORT_YYYYMMDD_...
    match = re.search(r'_(\d{8})_', game_id)
    if match:
        date_str = match.group(1)
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return None


def extract_ticker_date(ticker: str) -> Optional[str]:
    """Extract date from Kalshi ticker like KXATPMATCH-26JAN22CERRUB-RUB.

    Returns date in YYYY-MM-DD format or None if not found.
    Assumes year 2026 for tickers with format like 26JAN22.
    """
    # Match pattern like -26JAN22 or -26FEB04
    match = re.search(r'-26(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})', ticker.upper())
    if match:
        month_map = {
            'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
            'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
            'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
        }
        month = month_map[match.group(1)]
        day = match.group(2)
        return f"2026-{month}-{day}"
    return None


@dataclass
class BetOpportunity:
    """Represents a single bet opportunity."""

    sport: str
    ticker: str
    bet_on: str  # "home" or "away"
    team: str
    opponent: str
    elo_prob: float  # Elo-predicted win probability
    market_prob: float  # Market-implied probability
    edge: float  # elo_prob - market_prob
    confidence: str  # "HIGH" or "MEDIUM"
    yes_ask: float  # Market ask price (for buying)
    no_ask: float  # Market ask price (for buying)
    game_time: Optional[str] = None
    game_id: Optional[str] = None  # Game ID for cross-referencing
    betmgm_prob: Optional[float] = None  # BetMGM implied probability

    @property
    def kelly_fraction(self) -> float:
        """Calculate Kelly Criterion fraction for this bet.

        Kelly formula: f = (p*b - q) / b
        where:
        - p = probability of winning (elo_prob)
        - q = probability of losing (1 - elo_prob)
        - b = net odds (1/market_prob - 1)
        """
        if self.market_prob <= 0 or self.market_prob >= 1:
            return 0.0

        p = self.elo_prob
        q = 1 - p
        b = (1 / self.market_prob) - 1

        kelly = (p * b - q) / b
        return max(0, kelly)  # Never negative

    @property
    def expected_value(self) -> float:
        """Calculate expected value as percentage of stake."""
        return self.edge / self.market_prob


@dataclass
class PortfolioAllocation:
    """Represents optimized allocation for a bet."""

    opportunity: BetOpportunity
    bet_size: float
    kelly_fraction: float
    allocation_pct: float  # Percentage of bankroll


class PortfolioOptimizer:
    """Optimize bet sizing across all sports using Kelly Criterion and portfolio theory."""

    def __init__(
        self,
        bankroll: float,
        max_daily_risk_pct: float = 0.10,  # Max 10% of bankroll per day
        kelly_fraction: float = 0.25,  # Use 1/4 Kelly for safety
        min_bet_size: float = 2.0,
        max_bet_size: float = 50.0,
        max_single_bet_pct: float = 0.05,  # Max 5% per bet
        min_edge: float = 0.05,  # Minimum 5% edge
        min_confidence: float = 0.68,  # Minimum Elo probability required
        excluded_segments: Optional[List[Tuple[str, str]]] = None,  # List of (sport, confidence) tuples to exclude
    ):
        """Initialize portfolio optimizer.

        Args:
            bankroll: Total available capital
            max_daily_risk_pct: Maximum percentage of bankroll to risk per day
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
            min_bet_size: Minimum bet size in dollars
            max_bet_size: Maximum bet size in dollars
            max_single_bet_pct: Maximum percentage of bankroll for single bet
            min_edge: Minimum edge required to consider bet
            min_confidence: Minimum Elo probability required
            excluded_segments: List of (sport, confidence) tuples to exclude from betting.
                              Example: [("NHL", "MEDIUM"), ("TENNIS", "LOW")] to skip these segments.
        """
        self.bankroll = bankroll
        self.max_daily_risk_pct = max_daily_risk_pct
        self.kelly_fraction = kelly_fraction
        self.min_bet_size = min_bet_size
        self.max_bet_size = max_bet_size
        self.max_single_bet_pct = max_single_bet_pct
        self.min_edge = min_edge
        self.min_confidence = min_confidence
        self.excluded_segments = excluded_segments or []

    def _fetch_betmgm_prob(self, game_id: Optional[str], bet_direction: str) -> Optional[float]:
        """Fetch BetMGM implied probability from game_odds table.

        Args:
            game_id: Game ID to look up (format: SPORT_YYYYMMDD_HOME_AWAY)
            bet_direction: 'home' or 'away'

        Returns:
            BetMGM implied probability or None if not found
        """
        if not game_id:
            return None

        try:
            from db_manager import default_db
            from datetime import datetime, timedelta

            # Try exact match first (use :param style for SQLAlchemy)
            query = """
                SELECT outcome_name, price
                FROM game_odds
                WHERE game_id = :game_id
                  AND LOWER(bookmaker) = 'betmgm'
                  AND LOWER(market_name) = 'h2h'
            """
            result = default_db.fetch_df(query, {"game_id": game_id})

            # If exact match fails, try fuzzy match by sport and team names
            # game_id format: SPORT_YYYYMMDD_HOME_AWAY (e.g., NHL_20260129_STL_FLA)
            if result.empty:
                parts = game_id.split('_')
                if len(parts) >= 4:
                    sport = parts[0]
                    date_part = parts[1]  # YYYYMMDD
                    home_abbr = parts[2].upper()
                    away_abbr = parts[3].upper()

                    # Try current date first, then nearby dates (±1 day for timezone issues)
                    try:
                        base_date = datetime.strptime(date_part, '%Y%m%d')
                        dates_to_try = [
                            base_date.strftime('%Y%m%d'),
                            (base_date + timedelta(days=1)).strftime('%Y%m%d'),
                            (base_date - timedelta(days=1)).strftime('%Y%m%d'),
                        ]
                    except ValueError:
                        dates_to_try = [date_part]

                    for try_date in dates_to_try:
                        # Query for BetMGM odds matching sport, date, and team name patterns
                        fuzzy_query = """
                            SELECT game_id, outcome_name, price
                            FROM game_odds
                            WHERE LOWER(bookmaker) = 'betmgm'
                              AND LOWER(market_name) = 'h2h'
                              AND game_id LIKE :date_pattern
                              AND (
                                  UPPER(game_id) LIKE :home_pattern
                                  AND UPPER(game_id) LIKE :away_pattern
                              )
                        """
                        # Match pattern: SPORT_YYYYMMDD_*HOME*_*AWAY*
                        date_pattern = f"{sport}_{try_date}_%"
                        home_pattern = f"%{home_abbr}%"
                        away_pattern = f"%{away_abbr}%"

                        result = default_db.fetch_df(fuzzy_query, {
                            "date_pattern": date_pattern,
                            "home_pattern": home_pattern,
                            "away_pattern": away_pattern
                        })

                        if not result.empty:
                            break

            if result.empty:
                return None

            # Find the matching outcome (home or away)
            for _, row in result.iterrows():
                outcome = str(row.get('outcome_name', '')).lower()
                price = row.get('price', 0)

                if price and price > 0:
                    # Convert decimal odds to probability: prob = 1 / decimal_odds
                    prob = 1.0 / price

                    # Match bet_direction to outcome
                    if bet_direction == 'home' and outcome in ['home', 'h']:
                        return prob
                    elif bet_direction == 'away' and outcome in ['away', 'a']:
                        return prob

            return None

        except Exception:
            return None

    def load_opportunities_from_database(
        self,
        date_str: str,
        sports: List[str] = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"],
    ) -> List[BetOpportunity]:
        """Load all bet opportunities from PostgreSQL database for a given date.

        Args:
            date_str: Date in YYYY-MM-DD format
            sports: List of sports to check

        Returns:
            List of BetOpportunity objects
        """
        from db_manager import default_db

        opportunities = []
        today = date_str  # Use the passed date as "today" for filtering
        skipped_stale = 0

        # Build SQL query
        sports_list = ", ".join([f"'{sport}'" for sport in sports])
        query = f"""
            SELECT
                sport,
                ticker,
                bet_on,
                home_team,
                away_team,
                elo_prob,
                market_prob,
                edge,
                confidence,
                yes_ask,
                no_ask,
                recommendation_date,
                bet_id
            FROM bet_recommendations
            WHERE recommendation_date = :rec_date
                AND sport IN ({sports_list})
                AND ticker IS NOT NULL
                AND ticker != ''
            ORDER BY sport, home_team, away_team
        """

        try:
            results = default_db.fetch_df(query, {"rec_date": date_str})

            if results.empty:
                print(f"⚠️  No bet recommendations found in database for {date_str}")
                return opportunities

            print(f"📊 Loaded {len(results)} bet recommendations from database for {date_str}")

            for _, row in results.iterrows():
                sport = row["sport"]
                ticker = row["ticker"]

                # Skip if missing required fields or invalid ticker
                if not ticker or pd.isna(ticker):
                    continue

                # Filter out stale tickers (ticker date before today)
                ticker_date = extract_ticker_date(ticker)
                if ticker_date and ticker_date < today:
                    skipped_stale += 1
                    continue

                # Handle different sport structures
                try:
                    if sport == "tennis":
                        # For tennis, bet_on is player name
                        team = row["bet_on"]
                        opponent = row["away_team"] if team == row["home_team"] else row["home_team"]
                        bet_direction = "home"  # Default for tennis

                        # Market prob from yes_ask/no_ask
                        yes_ask = float(row["yes_ask"]) if row["yes_ask"] is not None else 0
                        no_ask = float(row["no_ask"]) if row["no_ask"] is not None else 0

                        # Use pre-calculated market_prob
                        market_prob = float(row["market_prob"])

                        # Estimate asks if missing so executing logic works later
                        if yes_ask == 0 and market_prob > 0:
                            yes_ask = int(market_prob * 100)
                        if no_ask == 0 and market_prob > 0:
                            no_ask = int((1 - market_prob) * 100)

                    elif sport == "ncaab":
                        # NCAAB has home/away
                        bet_direction = row["bet_on"]

                        if bet_direction == "home":
                            team = row["home_team"]
                            opponent = row["away_team"]
                        else:
                            team = row["away_team"]
                            opponent = row["home_team"]

                        # Try to get yes_ask/no_ask, fallback to calculating from market_prob
                        yes_ask = float(row["yes_ask"]) if row["yes_ask"] is not None else 0
                        no_ask = float(row["no_ask"]) if row["no_ask"] is not None else 0

                        if yes_ask == 0:
                            # Estimate prices from market_prob
                            mp = float(row["market_prob"])
                            yes_ask = int(mp * 100)
                            no_ask = int((1 - mp) * 100)

                        market_prob = float(row["market_prob"])

                    else:
                        # Traditional team sports (nba, nhl, mlb, nfl, epl, ligue1, wncaab)
                        bet_direction = row["bet_on"]

                        if bet_direction == "home":
                            team = row["home_team"]
                            opponent = row["away_team"]
                        else:
                            team = row["away_team"]
                            opponent = row["home_team"]

                        yes_ask = float(row["yes_ask"]) if row["yes_ask"] is not None else 0
                        no_ask = float(row["no_ask"]) if row["no_ask"] is not None else 0

                        if yes_ask == 0:
                            # Estimate prices from market_prob
                            mp = float(row["market_prob"])
                            yes_ask = int(mp * 100)
                            no_ask = int((1 - mp) * 100)

                        market_prob = float(row["market_prob"])

                    # Get game_id from bet data
                    game_id = row.get("bet_id", "")

                    # Create BetOpportunity object
                    opportunity = BetOpportunity(
                        sport=sport,
                        ticker=ticker,
                        bet_on=bet_direction,
                        team=team,
                        opponent=opponent,
                        elo_prob=float(row["elo_prob"]),
                        market_prob=market_prob,
                        edge=float(row["edge"]),
                        confidence=row["confidence"],
                        yes_ask=yes_ask,
                        no_ask=no_ask,
                        game_id=game_id,
                        game_time=None,  # Would need to join with unified_games to get this
                    )

                    # NOTE: BetMGM probability fetch removed - method was never implemented
                    # This was optional cross-checking with BetMGM odds

                    opportunities.append(opportunity)

                except (KeyError, ValueError, TypeError) as e:
                    print(f"⚠️  Error processing {sport} bet opportunity: {e}")
                    continue

        except Exception as e:
            print(f"❌ Error loading opportunities from database: {e}")
            import traceback
            traceback.print_exc()

        if skipped_stale > 0:
            print(f"⚠️  Skipped {skipped_stale} stale opportunities (ticker date before {today})")

        return opportunities

    def load_opportunities_from_files(
        self,
        date_str: str,
        sports: List[str] = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"],
    ) -> List[BetOpportunity]:
        """Load all bet opportunities from JSON files for a given date.

        Args:
            date_str: Date in YYYY-MM-DD format
            sports: List of sports to check

        Returns:
            List of BetOpportunity objects
        """
        opportunities = []
        today = date_str  # Use the passed date as "today" for filtering
        skipped_stale = 0

        for sport in sports:
            bet_file = Path(f"data/{sport}/bets_{date_str}.json")

            if not bet_file.exists():
                continue

            try:
                with open(bet_file, "r") as f:
                    bets_data = json.load(f)

                if not isinstance(bets_data, list):
                    continue

                for bet in bets_data:
                    # Skip if missing required fields or invalid ticker
                    if "ticker" not in bet:
                        continue

                    ticker = bet.get("ticker")
                    if not ticker or ticker is None:
                        # Skip None, empty string, or other falsy tickers
                        continue

                    # Filter out stale games (games before today)
                    game_id = bet.get("game_id", "")
                    game_date = extract_game_date(game_id)
                    if game_date and game_date < today:
                        skipped_stale += 1
                        continue

                    # Filter out stale tickers (ticker date before today)
                    # Kalshi tickers have dates like 26JAN22 embedded in them
                    ticker_date = extract_ticker_date(ticker)
                    if ticker_date and ticker_date < today:
                        skipped_stale += 1
                        continue

                    # Handle different sport structures
                    try:
                        if sport == "tennis":
                            # Tennis uses player1/player2 and bet_on is player name
                            team = bet.get("bet_on", bet.get("player1", ""))
                            opponent = bet.get("opponent", bet.get("player2", ""))
                            bet_direction = bet.get("side", "home")

                            # Market prob from yes_ask/no_ask
                            yes_ask = bet.get("yes_ask", 0)
                            no_ask = bet.get("no_ask", 0)

                            # First try to use pre-calculated market_prob
                            if "market_prob" in bet:
                                market_prob = bet["market_prob"]
                                # Estimate asks if missing so executing logic works later
                                if yes_ask == 0 and market_prob > 0:
                                    yes_ask = int(market_prob * 100)
                                if no_ask == 0 and market_prob > 0:
                                    # This is an estimate assuming balanced book, but we only need market_prob for kelly
                                    no_ask = int((1 - market_prob) * 100)
                            else:
                                # For tennis, need to figure out which side we're betting
                                # If bet_on matches player1, use yes_ask, otherwise no_ask
                                player1 = bet.get("player1", "")
                                if (
                                    team
                                    and player1
                                    and (team in player1 or player1 in team)
                                ):
                                    market_prob = yes_ask / 100
                                else:
                                    market_prob = no_ask / 100

                        elif sport == "ncaab":
                            # NCAAB has home/away but might be missing yes_ask/no_ask
                            bet_direction = bet.get("side", bet.get("bet_on", "home"))

                            if bet_direction == "home":
                                team = bet.get("home_team", "")
                                opponent = bet.get("away_team", "")
                            else:
                                team = bet.get("away_team", "")
                                opponent = bet.get("home_team", "")

                            # Try to get yes_ask/no_ask, fallback to calculating from market_prob
                            yes_ask = bet.get("yes_ask", 0)
                            no_ask = bet.get("no_ask", 0)

                            if yes_ask == 0 and "market_prob" in bet:
                                # Estimate prices from market_prob
                                mp = bet.get("market_prob", 0.5)
                                yes_ask = int(mp * 100)
                                no_ask = int((1 - mp) * 100)

                            if bet_direction == "home":
                                market_prob = (
                                    yes_ask / 100
                                    if yes_ask > 0
                                    else bet.get("market_prob", 0.5)
                                )
                            else:
                                market_prob = (
                                    no_ask / 100
                                    if no_ask > 0
                                    else bet.get("market_prob", 0.5)
                                )

                        else:
                            # Traditional team sports (nba, nhl, mlb, nfl)
                            bet_direction = bet.get("side", bet.get("bet_on", "home"))

                            if bet_direction == "home":
                                team = bet.get("home_team", "")
                                opponent = bet.get("away_team", "")
                            else:
                                team = bet.get("away_team", "")
                                opponent = bet.get("home_team", "")

                            yes_ask = bet.get("yes_ask", 0)
                            no_ask = bet.get("no_ask", 0)

                            if yes_ask == 0 and "market_prob" in bet:
                                mp = bet.get("market_prob", 0.5)
                                yes_ask = int(mp * 100)
                                no_ask = int((1 - mp) * 100)

                            if bet_direction == "home":
                                market_prob = (
                                    yes_ask / 100
                                    if yes_ask > 0
                                    else bet.get("market_prob", 0.5)
                                )
                            else:
                                market_prob = (
                                    no_ask / 100
                                    if no_ask > 0
                                    else bet.get("market_prob", 0.5)
                                )

                        # Skip if we couldn't determine market probability
                        if market_prob <= 0:
                            continue

                        # Get game_id from bet data
                        game_id = bet.get("game_id")

                        # Fetch BetMGM probability from database
                        betmgm_prob = self._fetch_betmgm_prob(game_id, bet_direction)

                        opportunity = BetOpportunity(
                            sport=sport,
                            ticker=bet["ticker"],
                            bet_on=bet_direction,
                            team=team,
                            opponent=opponent,
                            elo_prob=bet["elo_prob"],
                            market_prob=market_prob,
                            edge=bet["edge"],
                            confidence=bet["confidence"],
                            yes_ask=yes_ask,
                            no_ask=no_ask,
                            game_time=bet.get("game_time", bet.get("close_time")),
                            game_id=game_id,
                            betmgm_prob=betmgm_prob,
                        )

                        opportunities.append(opportunity)

                    except Exception:
                        # Skip individual bets that fail to parse
                        continue

            except Exception as e:
                print(f"⚠️  Error loading {bet_file}: {e}")

        if skipped_stale > 0:
            print(f"📅 Skipped {skipped_stale} stale opportunities (game date < {today})")

        return opportunities

    def filter_opportunities(
        self, opportunities: List[BetOpportunity]
    ) -> List[BetOpportunity]:
        """Filter opportunities based on minimum thresholds.

        For MARKET AGREEMENT strategy, we bet when Elo and market agree.
        Traditional edge/Kelly filters don't apply - we use different criteria.

        Excluded segments are sport+confidence combinations that have been
        identified as consistently unprofitable through backtest analysis.

        Args:
            opportunities: List of all opportunities

        Returns:
            Filtered list meeting minimum criteria
        """
        filtered = []
        excluded_count = 0

        for opp in opportunities:
            # Check excluded segments (e.g., NHL MEDIUM, TENNIS LOW)
            # These are sport+confidence combinations identified as unprofitable
            segment = (opp.sport.upper(), opp.confidence.upper())
            if segment in self.excluded_segments:
                excluded_count += 1
                continue

            # Check minimum edge (set to -1.0 for market agreement strategy)
            if opp.edge < self.min_edge:
                continue

            # Check minimum confidence (Elo probability)
            if opp.elo_prob < self.min_confidence:
                continue

            # For market agreement strategy, skip Kelly check if min_edge < 0
            # (this indicates we're using market agreement, not edge-based betting)
            if self.min_edge >= 0 and opp.kelly_fraction <= 0:
                continue

            filtered.append(opp)

        if excluded_count > 0:
            print(f"🚫 Excluded {excluded_count} opportunities from unprofitable segments: {self.excluded_segments}")

        return filtered

    def calculate_portfolio_allocation(
        self, opportunities: List[BetOpportunity]
    ) -> List[PortfolioAllocation]:
        """Calculate optimal bet sizes for portfolio of opportunities.

        For market agreement strategy (min_edge < 0), uses equal sizing across
        all opportunities to maximize bet count for law of large numbers.

        Args:
            opportunities: List of filtered bet opportunities

        Returns:
            List of PortfolioAllocation with bet sizes
        """
        if not opportunities:
            return []

        max_daily_allocation = self.bankroll * self.max_daily_risk_pct

        # For market agreement strategy, use equal sizing to maximize bet count
        if self.min_edge < 0:
            # Calculate how many bets we can afford with equal sizing
            # Minimum bet must be $1 to ensure at least 1 contract at any price (up to 99¢)
            min_practical_bet = 1.00
            max_bets = int(max_daily_allocation / min_practical_bet)

            # Limit to available opportunities
            num_bets = min(max_bets, len(opportunities))

            # Equal size for each bet
            if num_bets > 0:
                bet_size = max_daily_allocation / num_bets
                bet_size = min(bet_size, self.max_bet_size)
                bet_size = min(bet_size, self.bankroll * self.max_single_bet_pct)
                bet_size = max(bet_size, min_practical_bet)
            else:
                bet_size = min_practical_bet

            # Sort by expected value and allocate equal amounts
            sorted_opps = sorted(
                opportunities, key=lambda x: x.expected_value, reverse=True
            )

            allocations = []
            total_allocated = 0.0

            for opp in sorted_opps:
                if total_allocated + bet_size > max_daily_allocation:
                    break

                allocation = PortfolioAllocation(
                    opportunity=opp,
                    bet_size=round(bet_size, 2),
                    kelly_fraction=0.01,  # Nominal for market agreement
                    allocation_pct=bet_size / self.bankroll,
                )
                allocations.append(allocation)
                total_allocated += bet_size

            return allocations

        # Original Kelly-based allocation for edge-based strategy
        sorted_opps = sorted(
            opportunities, key=lambda x: x.expected_value, reverse=True
        )

        allocations = []
        total_allocated = 0.0

        for opp in sorted_opps:
            # Calculate Kelly bet size
            if opp.kelly_fraction > 0:
                kelly_size = self.bankroll * opp.kelly_fraction * self.kelly_fraction
            else:
                kelly_size = self.min_bet_size

            # Apply constraints
            bet_size = kelly_size
            bet_size = max(self.min_bet_size, bet_size)  # Minimum
            bet_size = min(self.max_bet_size, bet_size)  # Maximum
            bet_size = min(
                self.bankroll * self.max_single_bet_pct, bet_size
            )  # Per-bet limit

            # Check daily limit
            if total_allocated + bet_size > max_daily_allocation:
                remaining = max_daily_allocation - total_allocated
                if remaining < self.min_bet_size:
                    break  # Skip this and remaining bets
                bet_size = remaining

            allocation = PortfolioAllocation(
                opportunity=opp,
                bet_size=round(bet_size, 2),
                kelly_fraction=opp.kelly_fraction if opp.kelly_fraction > 0 else 0.01,
                allocation_pct=bet_size / self.bankroll,
            )

            allocations.append(allocation)
            total_allocated += bet_size

            # Stop if we've hit daily limit
            if total_allocated >= max_daily_allocation:
                break

        return allocations

    def optimize_daily_bets(
        self, date_str: str, sports: List[str] = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"],
        use_database: bool = True
    ) -> Tuple[List[PortfolioAllocation], Dict]:
        """Main entry point: Load, filter, and optimize bets for a given date.

        Args:
            date_str: Date in YYYY-MM-DD format
            sports: List of sports to include
            use_database: If True, load from PostgreSQL database; if False, load from JSON files

        Returns:
            Tuple of (allocations, summary_stats)
        """
        # Load opportunities
        if use_database:
            print(f"📊 Loading opportunities from database for {date_str}...")
            opportunities = self.load_opportunities_from_database(date_str, sports)
            if not opportunities:
                print(f"⚠️  No opportunities found in database, falling back to files...")
                opportunities = self.load_opportunities_from_files(date_str, sports)
        else:
            print(f"📊 Loading opportunities from files for {date_str}...")
            opportunities = self.load_opportunities_from_files(date_str, sports)

        # Filter by criteria
        filtered_opps = self.filter_opportunities(opportunities)

        # Calculate allocations
        allocations = self.calculate_portfolio_allocation(filtered_opps)

        # Calculate summary statistics
        total_bet = sum(a.bet_size for a in allocations)
        total_expected_profit = sum(
            a.bet_size * a.opportunity.expected_value for a in allocations
        )

        summary = {
            "date": date_str,
            "bankroll": self.bankroll,
            "data_source": "database" if use_database and opportunities else "files",
            "opportunities_found": len(opportunities),
            "opportunities_filtered": len(filtered_opps),
            "bets_placed": len(allocations),
            "total_bet_amount": round(total_bet, 2),
            "total_bet_pct": round(total_bet / self.bankroll, 4),
            "expected_profit": round(total_expected_profit, 2),
            "expected_roi": (
                round(total_expected_profit / total_bet, 4) if total_bet > 0 else 0
            ),
            "avg_bet_size": (
                round(total_bet / len(allocations), 2) if allocations else 0
            ),
            "avg_edge": (
                round(
                    sum(a.opportunity.edge for a in allocations) / len(allocations), 4
                )
                if allocations
                else 0
            ),
        }

        return allocations, summary

    def generate_bet_report(
        self,
        allocations: List[PortfolioAllocation],
        summary: Dict,
        output_file: Optional[Path] = None,
    ) -> str:
        """Generate human-readable betting report.

        Args:
            allocations: List of portfolio allocations
            summary: Summary statistics dictionary
            output_file: Optional path to save report

        Returns:
            Report as string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("PORTFOLIO-OPTIMIZED BETTING REPORT")
        lines.append("=" * 80)
        lines.append(f"Date: {summary['date']}")
        lines.append(f"Bankroll: ${summary['bankroll']:,.2f}")
        lines.append(
            f"Max Daily Risk: {self.max_daily_risk_pct:.1%} (${self.bankroll * self.max_daily_risk_pct:,.2f})"
        )
        lines.append(f"Kelly Fraction: {self.kelly_fraction:.2%}")
        lines.append("")

        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Opportunities Found:     {summary['opportunities_found']}")
        lines.append(f"After Filtering:         {summary['opportunities_filtered']}")
        lines.append(f"Bets to Place:           {summary['bets_placed']}")
        lines.append(
            f"Total Bet Amount:        ${summary['total_bet_amount']:,.2f} ({summary['total_bet_pct']:.2%} of bankroll)"
        )
        lines.append(f"Expected Profit:         ${summary['expected_profit']:,.2f}")
        lines.append(f"Expected ROI:            {summary['expected_roi']:.2%}")
        lines.append(f"Average Bet Size:        ${summary['avg_bet_size']:,.2f}")
        lines.append(f"Average Edge:            {summary['avg_edge']:.2%}")
        lines.append("")

        if allocations:
            lines.append("BET ALLOCATIONS")
            lines.append("-" * 80)

            # Group by sport
            by_sport = {}
            for alloc in allocations:
                sport = alloc.opportunity.sport.upper()
                if sport not in by_sport:
                    by_sport[sport] = []
                by_sport[sport].append(alloc)

            for sport in sorted(by_sport.keys()):
                lines.append(f"\n{sport}:")
                sport_total = sum(a.bet_size for a in by_sport[sport])
                lines.append(f"  Sport Total: ${sport_total:.2f}\n")

                for i, alloc in enumerate(by_sport[sport], 1):
                    opp = alloc.opportunity
                    lines.append(f"  {i}. {opp.team} vs {opp.opponent}")
                    lines.append(f"     Ticker: {opp.ticker}")
                    lines.append(
                        f"     Bet Size: ${alloc.bet_size:.2f} ({alloc.allocation_pct:.2%} of bankroll)"
                    )
                    lines.append(
                        f"     Elo Prob: {opp.elo_prob:.1%} | Market: {opp.market_prob:.1%} | Edge: {opp.edge:+.1%}"
                    )
                    lines.append(
                        f"     Kelly Fraction: {opp.kelly_fraction:.3f} (scaled: {alloc.kelly_fraction * self.kelly_fraction:.3f})"
                    )
                    lines.append(f"     Expected Value: {opp.expected_value:+.2%}")
                    lines.append(f"     Confidence: {opp.confidence}")
                    lines.append("")
        else:
            lines.append("No bets meet criteria.")

        lines.append("=" * 80)

        report = "\n".join(lines)

        if output_file:
            output_file.write_text(report)

        return report


def main():
    """Example usage of portfolio optimizer."""
    import sys

    # Get current date
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Example: $1000 bankroll
    bankroll = 1000.0

    optimizer = PortfolioOptimizer(
        bankroll=bankroll,
        max_daily_risk_pct=0.10,  # Max 10% of bankroll per day
        kelly_fraction=0.25,  # Quarter Kelly
        min_bet_size=2.0,
        max_bet_size=50.0,
        max_single_bet_pct=0.05,  # Max 5% per bet
        min_edge=0.05,
        min_confidence=0.68,
    )

    allocations, summary = optimizer.optimize_daily_bets(date_str)
    report = optimizer.generate_bet_report(allocations, summary)

    print(report)


if __name__ == "__main__":
    main()
