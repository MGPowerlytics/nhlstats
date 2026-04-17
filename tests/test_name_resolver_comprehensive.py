"""Regression tests for production name resolution behavior."""

from plugins.naming_resolver import NamingContext, NamingResolver


def _resolve_to_elo_name(sport: str, raw_name: str) -> str:
    """Resolve a sportsbook-facing name to the final Elo-facing name."""
    canonical_name = NamingResolver.resolve(
        NamingContext(sport=sport, source="kalshi", name=raw_name)
    )
    return NamingResolver.resolve(
        NamingContext(sport=sport, source="elo", name=canonical_name)
    )


class TestNameResolverFixes:
    """Smoke tests for the most important resolver regressions."""

    def test_epl_mappings(self) -> None:
        """EPL abbreviations and aliases should resolve to current Elo names."""
        epl_cases = [
            ("WHU", "West Ham"),
            ("WOL", "Wolves"),
            ("LFC", "Liverpool"),
            ("FUL", "Fulham"),
            ("MCI", "Man City"),
            ("MUN", "Man United"),
            ("CHE", "Chelsea"),
            ("TOT", "Tottenham"),
            ("ARS", "Arsenal"),
            ("AVL", "Aston Villa"),
            ("NEW", "Newcastle"),
            ("BHA", "Brighton"),
            ("CRY", "Crystal Palace"),
            ("BRE", "Brentford"),
            ("EVE", "Everton"),
            ("LEE", "Leeds"),
            ("LEI", "Leicester"),
            ("SOU", "Southampton"),
            ("BOU", "Bournemouth"),
            ("NFO", "Nott'm Forest"),
        ]

        for raw_name, expected_name in epl_cases:
            resolved_name = _resolve_to_elo_name("epl", raw_name)
            assert (
                resolved_name == expected_name
            ), f"EPL: {raw_name} -> {resolved_name} (expected: {expected_name})"

    def test_nba_mappings_no_cross_sport(self) -> None:
        """NBA abbreviations should resolve to NBA Elo names, not other sports."""
        nba_cases = [
            ("ATL", "ATL"),
            ("MIA", "MIA"),
            ("CLE", "CLE"),
            ("LAL", "LAL"),
            ("GSW", "GSW"),
            ("BOS", "BOS"),
            ("CHI", "CHI"),
            ("DAL", "DAL"),
            ("DEN", "DEN"),
            ("HOU", "HOU"),
            ("LAC", "LAC"),
            ("MEM", "MEM"),
            ("MIL", "MIL"),
            ("MIN", "MIN"),
            ("NOP", "NOP"),
            ("NYK", "NYK"),
            ("OKC", "OKC"),
            ("ORL", "ORL"),
            ("PHI", "PHI"),
            ("PHX", "PHX"),
            ("POR", "POR"),
            ("SAC", "SAC"),
            ("SAS", "SAS"),
            ("TOR", "TOR"),
            ("UTA", "UTA"),
            ("WAS", "WAS"),
        ]

        for raw_name, expected_name in nba_cases:
            resolved_name = _resolve_to_elo_name("nba", raw_name)
            assert (
                resolved_name == expected_name
            ), f"NBA: {raw_name} -> {resolved_name} (expected: {expected_name})"

    def test_mlb_mappings(self) -> None:
        """MLB abbreviations should resolve to current Elo names."""
        mlb_cases = [
            ("LAD", "Los Angeles Dodgers"),
            ("TEX", "Texas Rangers"),
            ("HOU", "Houston Astros"),
            ("SEA", "Seattle Mariners"),
            ("NYY", "New York Yankees"),
            ("BOS", "Boston Red Sox"),
            ("CHC", "Chicago Cubs"),
            ("ATL", "Atlanta Braves"),
            ("MIA", "Miami Marlins"),
            ("CLE", "Cleveland Guardians"),
        ]

        for raw_name, expected_name in mlb_cases:
            resolved_name = _resolve_to_elo_name("mlb", raw_name)
            assert (
                resolved_name == expected_name
            ), f"MLB: {raw_name} -> {resolved_name} (expected: {expected_name})"

    def test_nhl_mappings(self) -> None:
        """NHL abbreviations and edge aliases should resolve to Elo names."""
        nhl_cases = [
            ("ANA", "ANA"),
            ("BOS", "BOS"),
            ("CHI", "CHI"),
            ("DET", "DET"),
            ("NYR", "NYR"),
            ("TOR", "TOR"),
            ("MTL", "MTL"),
            ("VAN", "VAN"),
            ("LA", "LAK"),
            ("NJ", "NJD"),
            ("SJ", "SJS"),
            ("TB", "TBL"),
        ]

        for raw_name, expected_name in nhl_cases:
            resolved_name = _resolve_to_elo_name("nhl", raw_name)
            assert (
                resolved_name == expected_name
            ), f"NHL: {raw_name} -> {resolved_name} (expected: {expected_name})"

    def test_full_names_resolve_to_elo_targets(self) -> None:
        """Full names should still resolve to the correct Elo-facing names."""
        full_name_cases = [
            ("epl", "Manchester City", "Man City"),
            ("epl", "West Ham United", "West Ham"),
            ("nba", "Los Angeles Lakers", "LAL"),
            ("nba", "Golden State Warriors", "GSW"),
            ("mlb", "Los Angeles Dodgers", "Los Angeles Dodgers"),
            ("mlb", "Texas Rangers", "Texas Rangers"),
            ("nhl", "Tampa Bay Lightning", "TBL"),
            ("nhl", "Los Angeles Kings", "LAK"),
        ]

        for sport, raw_name, expected_name in full_name_cases:
            resolved_name = _resolve_to_elo_name(sport, raw_name)
            assert resolved_name == expected_name, (
                f"Full name: {sport} {raw_name} -> {resolved_name} "
                f"(expected: {expected_name})"
            )
