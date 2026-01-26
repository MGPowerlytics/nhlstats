"""
Stub naming resolver for team name normalization across data sources.
TODO: Implement proper mapping database.
"""


class NamingResolver:
    @staticmethod
    def resolve(sport: str, source: str, name: str) -> str:
        """Return canonical name for a team/player.

        Args:
            sport: Sport identifier (e.g., 'nba', 'nhl')
            source: Data source ('kalshi', 'the_odds_api', 'elo')
            name: Raw team/player name from source

        Returns:
            Canonical name (currently returns input unchanged)
        """
        # Simple stub: return input unchanged
        return name
