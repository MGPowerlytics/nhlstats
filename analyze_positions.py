#!/usr/bin/env python3
"""
Kalshi Position Analysis Report Generator

Fetches open and recently closed positions from Kalshi API, compares them
with current Elo ratings, and generates a markdown report.

Usage:
    python analyze_positions.py [--days N]

Options:
    --days N    Include fills from last N days (default: 7)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import json
import argparse

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / "plugins"))

from kalshi_betting import KalshiBetting


class PositionAnalyzer:
    """Analyzes Kalshi positions against Elo ratings."""

    def __init__(self, api_key_id: str, private_key_path: str):
        self.client = KalshiBetting(api_key_id, private_key_path, production=True)
        self.ratings = self._load_all_ratings()
        self.team_mappings = self._load_team_mappings()

    def _load_all_ratings(self):
        """Load Elo ratings for all sports."""
        ratings = {}

        rating_files = {
            "nba": "data/nba_current_elo_ratings.csv",
            "ncaab": "data/ncaab_current_elo_ratings.csv",
            "wncaab": "data/wncaab_current_elo_ratings.csv",
            "atp": "data/atp_current_elo_ratings.csv",
            "wta": "data/wta_current_elo_ratings.csv",
        }

        for sport, filepath in rating_files.items():
            try:
                with open(filepath) as f:
                    next(f)  # Skip header
                    for line in f:
                        if line.strip():
                            parts = line.strip().split(",")
                            if len(parts) >= 2:
                                player, rating = parts[0], parts[1]
                                ratings[player] = float(rating)
            except FileNotFoundError:
                continue

        return ratings

    def _load_team_mappings(self):
        """Load team name mappings from Kalshi to our DB format."""
        mappings = {}

        mapping_files = {
            "nba": "data/nba_team_mapping.json",
            "ncaab": "data/ncaab_team_mapping.json",
        }

        for sport, filepath in mapping_files.items():
            try:
                with open(filepath) as f:
                    mappings[sport] = json.load(f)
            except FileNotFoundError:
                mappings[sport] = {}

        return mappings

    def get_positions(self, days_back=7):
        """Get all positions (open and recently closed)."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        # Get all fills
        response = self.client._get("/trade-api/v2/portfolio/fills")
        fills = response.get("fills", [])

        # Group by ticker
        positions = defaultdict(lambda: {"yes": 0, "no": 0, "fills": []})

        for fill in fills:
            ticker = fill.get("ticker", "")
            side = fill.get("side", "")
            action = fill.get("action", "")
            count = fill.get("count", 0)
            created = fill.get("created_time", "")

            # Parse date
            fill_date = datetime.fromisoformat(created.replace("Z", "+00:00"))

            # Track all fills
            positions[ticker]["fills"].append(fill)

            # Build net position
            if action == "buy":
                positions[ticker][side] += count
            elif action == "sell":
                positions[ticker][side] -= count

        return positions

    def classify_sport(self, ticker):
        """Determine sport from ticker."""
        if "NBAGAME" in ticker:
            return "nba"
        elif "NCAAMBGAME" in ticker:
            return "ncaab"
        elif "NCAAWBGAME" in ticker:
            return "wncaab"
        elif "ATP" in ticker or "WTA" in ticker:
            return "tennis"
        elif "NHLGAME" in ticker:
            return "nhl"
        else:
            return "other"

    def get_market_details(self, ticker):
        """Get market title and status."""
        try:
            market = self.client.get_market_details(ticker)
            if market:
                return {
                    "title": market.get("title", ticker),
                    "status": market.get("status", "unknown"),
                    "close_time": market.get("close_time"),
                }
        except:
            pass
        return {"title": ticker, "status": "unknown", "close_time": None}

    def analyze_position(self, ticker, position_data, market_details):
        """Analyze a single position against Elo ratings."""
        yes_contracts = position_data["yes"]
        no_contracts = position_data["no"]

        if yes_contracts > 0:
            net_side = "YES"
            net_count = yes_contracts
        elif no_contracts > 0:
            net_side = "NO"
            net_count = no_contracts
        else:
            return None

        sport = self.classify_sport(ticker)
        title = market_details["title"]

        analysis = {
            "ticker": ticker,
            "sport": sport,
            "title": title,
            "status": market_details["status"],
            "position_side": net_side,
            "position_count": net_count,
            "elo_analysis": None,
            "concerns": [],
        }

        # Parse and analyze based on sport
        if sport in ["nba", "ncaab", "wncaab"]:
            analysis.update(self._analyze_basketball(title, net_side, sport))
        elif sport == "tennis":
            analysis.update(self._analyze_tennis(title, net_side))

        return analysis

    def _analyze_basketball(self, title, net_side, sport):
        """Analyze basketball game position."""
        if " at " not in title:
            return {"elo_analysis": "Cannot parse teams"}

        parts = title.split(" at ")
        away_str = parts[0].strip()
        home_str = parts[1].replace(" Winner?", "").strip()

        # Map team names
        home_team = self._find_team(home_str, sport)
        away_team = self._find_team(away_str, sport)

        if not home_team or not away_team:
            return {
                "elo_analysis": f"Teams not found: {home_str} / {away_str}",
                "concerns": ["Teams not in Elo database"],
            }

        home_elo = self.ratings.get(home_team, 1500) + 100  # Home advantage
        away_elo = self.ratings.get(away_team, 1500)
        prob = 1 / (1 + 10 ** ((away_elo - home_elo) / 400))

        threshold = 0.65 if sport in ["ncaab", "wncaab"] else 0.64

        # Determine which team user bet on
        bet_team = home_team if net_side == "YES" else away_team
        bet_prob = prob if net_side == "YES" else (1 - prob)

        concerns = []
        if bet_prob < threshold:
            concerns.append(f"Below threshold ({threshold:.0%}): {bet_prob:.1%}")
        elif bet_prob < 0.50:
            concerns.append(f"Betting on underdog: {bet_prob:.1%}")

        return {
            "elo_analysis": f"{home_team} ({self.ratings.get(home_team, 1500):.0f}) vs {away_team} ({self.ratings.get(away_team, 1500):.0f}) → {prob:.1%}",
            "bet_on_team": bet_team,
            "bet_team_probability": bet_prob,
            "elo_probability": prob,
            "threshold": threshold,
            "concerns": concerns,
        }

    def _analyze_tennis(self, title, net_side):
        """Analyze tennis match position."""
        # Parse "Will X win the Y vs Z" format
        # Strategy: Extract BOTH names from the match portion (after "win the")
        # because those match our database format (last names)
        
        if "Will " in title and " win the " in title:
            # Get the match portion after "win the"
            match_portion = title.split(" win the ")[1]
            
            # Also get who the question is about (for ordering)
            question_about = title.replace("Will ", "").split(" win ")[0].strip()
            question_last = question_about.split()[-1].lower()
            
            if " vs " in match_portion:
                # Extract both players from match portion
                parts = match_portion.split(" vs ")
                match_p1 = parts[0].strip()
                match_p2 = parts[1].split(":")[0].strip()
                
                # Determine which match player the question is about
                if question_last in match_p1.lower():
                    # Question is about player 1
                    p1_text = match_p1
                    p2_text = match_p2
                elif question_last in match_p2.lower():
                    # Question is about player 2
                    p1_text = match_p2
                    p2_text = match_p1
                else:
                    # Fallback: use match order
                    p1_text = match_p1
                    p2_text = match_p2
            else:
                return {"elo_analysis": "Cannot parse players - no vs in match"}
        elif " vs " in title:
            # Simple "X vs Y" format
            parts = title.split(" vs ")
            p1_text = parts[0].strip()
            p2_text = parts[1].split(":")[0].strip()
        else:
            return {"elo_analysis": "Cannot parse players"}

        # Find players in ratings using just the names from match portion
        p1 = self._find_player(p1_text)
        p2 = self._find_player(p2_text)

        if not p1 or not p2 or p1 == p2:
            return {
                "elo_analysis": f"Players not found or duplicate: '{p1_text}' → {p1} / '{p2_text}' → {p2}",
                "concerns": ["Players not in Elo database or parsing error"],
            }

        r1 = self.ratings[p1]
        r2 = self.ratings[p2]
        prob = 1 / (1 + 10 ** ((r2 - r1) / 400))

        # Determine who user bet on
        # p1 is the player the question is about (or first in match)
        bet_player = p1 if net_side == "YES" else p2
        bet_prob = prob if net_side == "YES" else (1 - prob)

        threshold = 0.60
        concerns = []

        if bet_prob < threshold:
            concerns.append(f"Below threshold: {bet_prob:.1%}")
        if net_side == "YES" and prob < 0.50:
            concerns.append(f"Betting YES on {p1} but Elo only {prob:.1%}")
        elif net_side == "NO" and prob > 0.50:
            concerns.append(f"Betting NO (for {p2}) but {p1} favored at {prob:.1%}")

        return {
            "elo_analysis": f"{p1} ({r1:.0f}) vs {p2} ({r2:.0f}) → P({p1})={prob:.1%}",
            "bet_on_player": bet_player,
            "bet_player_probability": bet_prob,
            "elo_probability": prob,
            "threshold": threshold,
            "concerns": concerns,
        }

    def _find_team(self, team_str, sport):
        """Find team in ratings using mappings."""
        # Try mapping first
        if sport in self.team_mappings:
            mapped = self.team_mappings[sport].get(team_str)
            if mapped and mapped in self.ratings:
                return mapped

        # Try direct match
        if team_str in self.ratings:
            return team_str

        # Try substring match
        team_lower = team_str.lower()
        for team in self.ratings.keys():
            if team_lower in team.lower() or team.lower() in team_lower:
                return team

        return None

    def _find_player(self, player_str):
        """Find player in ratings using fuzzy matching."""
        player_lower = player_str.lower()

        # Try exact match
        for player in self.ratings.keys():
            if player_lower in player.lower():
                return player

        # Try last name match
        if " " in player_str:
            last_name = player_str.split()[-1].lower()
            for player in self.ratings.keys():
                if last_name in player.lower():
                    return player

        return None

    def generate_report(self, days_back=7):
        """Generate complete markdown report."""
        positions = self.get_positions(days_back)

        # Categorize positions
        open_positions = []
        closed_positions = []

        for ticker, pos_data in positions.items():
            market_details = self.get_market_details(ticker)
            analysis = self.analyze_position(ticker, pos_data, market_details)

            if analysis:
                if analysis["status"] in ["active", "open"]:
                    open_positions.append(analysis)
                else:
                    closed_positions.append(analysis)

        # Generate markdown
        report = self._generate_markdown(open_positions, closed_positions, days_back)
        return report

    def _generate_markdown(self, open_positions, closed_positions, days_back):
        """Generate markdown report."""
        now = datetime.utcnow()
        lines = []

        # Header
        lines.append("# Kalshi Position Analysis Report")
        lines.append(f"\n**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"**Period:** Last {days_back} days\n")

        # Account summary
        try:
            balance, portfolio_value = self.client.get_balance()
            lines.append("## Account Summary\n")
            lines.append(f"- **Balance:** ${balance:.2f}")
            lines.append(f"- **Portfolio Value:** ${portfolio_value:.2f}")
            lines.append(f"- **Total:** ${balance + portfolio_value:.2f}\n")
        except:
            pass

        # Open positions
        lines.append(f"## Open Positions ({len(open_positions)})\n")

        if open_positions:
            concerns_count = sum(1 for p in open_positions if p.get("concerns"))
            lines.append(f"**Status:** {concerns_count} positions with concerns\n")

            # Group by sport
            by_sport = defaultdict(list)
            for pos in open_positions:
                by_sport[pos["sport"]].append(pos)

            for sport in sorted(by_sport.keys()):
                lines.append(f"### {sport.upper()}\n")

                for pos in by_sport[sport]:
                    status_icon = "⚠️" if pos.get("concerns") else "✅"
                    lines.append(f"{status_icon} **{pos['title']}**")

                    # Show which team/player was bet on
                    bet_on = pos.get("bet_on_team") or pos.get("bet_on_player")
                    if bet_on:
                        lines.append(
                            f"- **Betting on: {bet_on}** ({pos['position_side']} × {pos['position_count']})"
                        )
                    else:
                        lines.append(
                            f"- Position: {pos['position_side']} × {pos['position_count']}"
                        )

                    if pos.get("elo_analysis"):
                        lines.append(f"- Elo: {pos['elo_analysis']}")

                    # Show bet probability if available
                    if pos.get("bet_player_probability") or pos.get(
                        "bet_team_probability"
                    ):
                        bet_prob = pos.get("bet_player_probability") or pos.get(
                            "bet_team_probability"
                        )
                        threshold = pos.get("threshold", 0)
                        if threshold and bet_prob >= threshold:
                            lines.append(
                                f"- ✅ Above threshold ({threshold:.0%}) - {bet_prob:.1%}"
                            )
                        elif bet_prob >= 0.50:
                            lines.append(
                                f"- ➡️ Favored but below threshold - {bet_prob:.1%}"
                            )
                        else:
                            lines.append(f"- ⚠️ Betting on underdog - {bet_prob:.1%}")
                    elif pos.get("elo_probability"):
                        threshold = pos.get("threshold", 0)
                        prob = pos["elo_probability"]
                        if threshold and prob >= threshold:
                            lines.append(f"- ✅ Above threshold ({threshold:.0%})")
                        elif prob >= 0.50:
                            lines.append(f"- ➡️ Favored but below threshold")
                        else:
                            lines.append(f"- ⚠️ Betting on underdog")

                    if pos.get("concerns"):
                        for concern in pos["concerns"]:
                            lines.append(f"- ⚠️ {concern}")
                    lines.append("")

        else:
            lines.append("*No open positions*\n")

        # Recently closed
        lines.append(f"## Recently Closed ({len(closed_positions)})\n")

        if closed_positions:
            by_sport = defaultdict(list)
            for pos in closed_positions:
                by_sport[pos["sport"]].append(pos)

            for sport in sorted(by_sport.keys()):
                lines.append(f"### {sport.upper()}\n")

                for pos in by_sport[sport][:10]:  # Limit to 10 per sport
                    lines.append(f"- **{pos['title']}**")
                    lines.append(
                        f"  - Position: {pos['position_side']} × {pos['position_count']}"
                    )
                    lines.append(f"  - Status: {pos['status']}")
                    if pos.get("elo_analysis"):
                        lines.append(f"  - Elo: {pos['elo_analysis']}")
                lines.append("")
        else:
            lines.append("*No recently closed positions*\n")

        # Summary
        lines.append("## Summary\n")
        lines.append(f"- Total Open Positions: {len(open_positions)}")
        lines.append(f"- Recently Closed: {len(closed_positions)}")

        concerns = [p for p in open_positions if p.get("concerns")]
        if concerns:
            lines.append(f"- Positions with Concerns: {len(concerns)}")

        lines.append("\n---\n*Generated by analyze_positions.py*")

        return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Kalshi positions against Elo ratings"
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Include positions from last N days"
    )
    args = parser.parse_args()

    # Load credentials
    try:
        with open("kalshkey") as f:
            api_key_id = f.read().split("\n")[0].split(":")[1].strip()
    except Exception as e:
        print(f"❌ Failed to load Kalshi credentials: {e}")
        return 1

    private_key_path = "data/kalshi_private_key.pem"

    # Create analyzer
    print("📊 Analyzing Kalshi positions...")
    analyzer = PositionAnalyzer(api_key_id, private_key_path)

    # Generate report
    report = analyzer.generate_report(days_back=args.days)

    # Save report
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"{timestamp}_positions_report.md"

    with open(report_path, "w") as f:
        f.write(report)

    print(f"✅ Report saved to: {report_path}")
    print(f"📄 {len(report.split(chr(10)))} lines generated")

    return 0


if __name__ == "__main__":
    sys.exit(main())
