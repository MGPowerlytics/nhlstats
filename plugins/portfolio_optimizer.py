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
from pathlib import Path


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
        min_confidence: float = 0.68,  # Minimum Elo probability
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
        """
        self.bankroll = bankroll
        self.max_daily_risk_pct = max_daily_risk_pct
        self.kelly_fraction = kelly_fraction
        self.min_bet_size = min_bet_size
        self.max_bet_size = max_bet_size
        self.max_single_bet_pct = max_single_bet_pct
        self.min_edge = min_edge
        self.min_confidence = min_confidence

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
                        )

                        opportunities.append(opportunity)

                    except Exception:
                        # Skip individual bets that fail to parse
                        continue

            except Exception as e:
                print(f"⚠️  Error loading {bet_file}: {e}")

        return opportunities

    def filter_opportunities(
        self, opportunities: List[BetOpportunity]
    ) -> List[BetOpportunity]:
        """Filter opportunities based on minimum thresholds.

        Args:
            opportunities: List of all opportunities

        Returns:
            Filtered list meeting minimum criteria
        """
        filtered = []

        for opp in opportunities:
            # Check minimum edge
            if opp.edge < self.min_edge:
                continue

            # Check minimum confidence (Elo probability)
            if opp.elo_prob < self.min_confidence:
                continue

            # Check Kelly is positive
            if opp.kelly_fraction <= 0:
                continue

            filtered.append(opp)

        return filtered

    def calculate_portfolio_allocation(
        self, opportunities: List[BetOpportunity]
    ) -> List[PortfolioAllocation]:
        """Calculate optimal bet sizes for portfolio of opportunities.

        Uses fractional Kelly Criterion with portfolio-level constraints.

        Args:
            opportunities: List of filtered bet opportunities

        Returns:
            List of PortfolioAllocation with bet sizes
        """
        if not opportunities:
            return []

        # Sort by expected value (best opportunities first)
        sorted_opps = sorted(
            opportunities, key=lambda x: x.expected_value, reverse=True
        )

        allocations = []
        total_allocated = 0.0
        max_daily_allocation = self.bankroll * self.max_daily_risk_pct

        for opp in sorted_opps:
            # Calculate Kelly bet size
            kelly_size = self.bankroll * opp.kelly_fraction * self.kelly_fraction

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
                kelly_fraction=opp.kelly_fraction,
                allocation_pct=bet_size / self.bankroll,
            )

            allocations.append(allocation)
            total_allocated += bet_size

            # Stop if we've hit daily limit
            if total_allocated >= max_daily_allocation:
                break

        return allocations

    def optimize_daily_bets(
        self, date_str: str, sports: List[str] = ["nhl", "nba", "mlb", "nfl"]
    ) -> Tuple[List[PortfolioAllocation], Dict]:
        """Main entry point: Load, filter, and optimize bets for a given date.

        Args:
            date_str: Date in YYYY-MM-DD format
            sports: List of sports to include

        Returns:
            Tuple of (allocations, summary_stats)
        """
        # Load opportunities
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
