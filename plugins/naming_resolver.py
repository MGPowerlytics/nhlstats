"""
Stub naming resolver for team name normalization across data sources.
TODO: Implement proper mapping database.
"""


class NamingResolver:
    # Class-level mapping storage
    _mappings = {}

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

    @staticmethod
    def add_mapping(sport: str, source: str, raw_name: str, canonical_name: str) -> None:
        """Add a mapping from raw name to canonical name.

        Args:
            sport: Sport identifier (e.g., 'nba', 'nhl')
            source: Data source ('kalshi', 'the_odds_api', 'elo')
            raw_name: Raw team/player name from source
            canonical_name: Canonical/normalized name
        """
        key = (sport.lower(), source.lower(), raw_name.lower())
        NamingResolver._mappings[key] = canonical_name
