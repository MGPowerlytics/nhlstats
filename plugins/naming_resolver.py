"""
Stub naming resolver for team name normalization across data sources.
TODO: Implement proper mapping database.
"""


class NamingResolver:
    # Class-level mapping storage
    _mappings = {
        # NCAAB
        ("ncaab", "kalshi", "hou"): "Houston",
        ("ncaab", "kalshi", "pur"): "Purdue",
        ("ncaab", "kalshi", "aub"): "Auburn",
        ("ncaab", "kalshi", "ala"): "Alabama",
        ("ncaab", "kalshi", "byu"): "BYU",
        ("ncaab", "kalshi", "uga"): "Georgia",
        ("ncaab", "kalshi", "lsu"): "LSU",
        ("ncaab", "kalshi", "day"): "Dayton",
        ("ncaab", "kalshi", "vcu"): "VCU",
        ("ncaab", "kalshi", "kan"): "Kansas",
        ("ncaab", "kalshi", "ken"): "Kentucky",
        ("ncaab", "kalshi", "duk"): "Duke",
        ("ncaab", "kalshi", "unc"): "North_Carolina",
        ("ncaab", "kalshi", "az"): "Arizona",
        ("ncaab", "kalshi", "gonz"): "Gonzaga",
        ("ncaab", "kalshi", "conn"): "Connecticut",
        ("ncaab", "kalshi", "tenn"): "Tennessee",
        ("ncaab", "kalshi", "isu"): "Iowa_St",
        ("ncaab", "kalshi", "bay"): "Baylor",
        ("ncaab", "kalshi", "ore"): "Oregon",
        ("ncaab", "kalshi", "ksu"): "Kansas_St",
        ("ncaab", "kalshi", "fiu"): "Florida_Intl",
        ("ncaab", "kalshi", "tcu"): "TCU",
        ("ncaab", "kalshi", "wis"): "Wisconsin",
        ("ncaab", "kalshi", "ind"): "Indiana",
        ("ncaab", "kalshi", "wku"): "Western_Kentucky",
        ("ncaab", "kalshi", "slu"): "Saint_Louis",
        ("ncaab", "kalshi", "uvm"): "Vermont",
        ("ncaab", "kalshi", "sfa"): "Stephen_F._Austin",
        ("ncaab", "kalshi", "lmu"): "Loyola_Marymount",
        ("ncaab", "kalshi", "quc"): "Queens_University",
        ("ncaab", "kalshi", "app"): "Appalachian_St",
        ("ncaab", "kalshi", "und"): "North_Dakota",
        ("ncaab", "kalshi", "cin"): "Cincinnati",
        ("ncaab", "kalshi", "wvu"): "West_Virginia",
        ("ncaab", "kalshi", "tex"): "Texas",
        # Add ELO mappings for canonical lookup
        ("ncaab", "elo", "houston"): "Houston",
        ("ncaab", "elo", "purdue"): "Purdue",
        ("ncaab", "elo", "auburn"): "Auburn",
        ("ncaab", "elo", "alabama"): "Alabama",
        ("ncaab", "elo", "byu"): "BYU",
        ("ncaab", "elo", "georgia"): "Georgia",
        ("ncaab", "elo", "lsu"): "LSU",
        ("ncaab", "elo", "dayton"): "Dayton",
        ("ncaab", "elo", "vcu"): "VCU",
        ("ncaab", "elo", "kansas"): "Kansas",
        ("ncaab", "elo", "kentucky"): "Kentucky",
        ("ncaab", "elo", "duke"): "Duke",
        ("ncaab", "elo", "north_carolina"): "North_Carolina",
        ("ncaab", "elo", "arizona"): "Arizona",
        ("ncaab", "elo", "gonzaga"): "Gonzaga",
        ("ncaab", "elo", "connecticut"): "Connecticut",
        ("ncaab", "elo", "tennessee"): "Tennessee",
        ("ncaab", "elo", "iowa_st"): "Iowa_St",
        ("ncaab", "elo", "baylor"): "Baylor",
        ("ncaab", "elo", "oregon"): "Oregon",
        ("ncaab", "elo", "kansas_st"): "Kansas_St",
        ("ncaab", "elo", "florida_intl"): "Florida_Intl",
        ("ncaab", "elo", "tcu"): "TCU",
        ("ncaab", "elo", "wisconsin"): "Wisconsin",
        ("ncaab", "elo", "indiana"): "Indiana",
        ("ncaab", "elo", "western_kentucky"): "Western_Kentucky",
        ("ncaab", "elo", "saint_louis"): "Saint_Louis",
        ("ncaab", "elo", "vermont"): "Vermont",
        ("ncaab", "elo", "stephen_f._austin"): "Stephen_F._Austin",
        ("ncaab", "elo", "loyola_marymount"): "Loyola_Marymount",
        ("ncaab", "elo", "queens_university"): "Queens_University",
        ("ncaab", "elo", "appalachian_st"): "Appalachian_St",
        ("ncaab", "elo", "north_dakota"): "North_Dakota",
        ("ncaab", "elo", "cincinnati"): "Cincinnati",
        ("ncaab", "elo", "west_virginia"): "West_Virginia",
        ("ncaab", "elo", "texas"): "Texas",
        # WNCAAB (using common abbreviations from Kalshi)
        ("wncaab", "kalshi", "van"): "Vanderbilt",
        ("wncaab", "kalshi", "fla"): "Florida",
        ("wncaab", "kalshi", "ark"): "Arkansas",
        ("wncaab", "kalshi", "aub"): "Auburn",
        ("wncaab", "kalshi", "lsu"): "LSU",
        ("wncaab", "kalshi", "tex"): "Texas",
        ("wncaab", "kalshi", "ala"): "Alabama",
        ("wncaab", "kalshi", "miss"): "Ole_Miss",
        ("wncaab", "kalshi", "msu"): "Mississippi_St",
        ("wncaab", "kalshi", "tenn"): "Tennessee",
        ("wncaab", "kalshi", "sc"): "South_Carolina",
        ("wncaab", "kalshi", "uk"): "Kentucky",
        ("wncaab", "kalshi", "uga"): "Georgia",
        ("wncaab", "kalshi", "mizz"): "Missouri",
        ("wncaab", "kalshi", "tamu"): "Texas_A&M",
        # WNCAAB ELO
        ("wncaab", "elo", "vanderbilt"): "Vanderbilt",
        ("wncaab", "elo", "florida"): "Florida",
        ("wncaab", "elo", "arkansas"): "Arkansas",
        ("wncaab", "elo", "auburn"): "Auburn",
        ("wncaab", "elo", "lsu"): "LSU",
        ("wncaab", "elo", "texas"): "Texas",
        ("wncaab", "elo", "alabama"): "Alabama",
        ("wncaab", "elo", "ole_miss"): "Ole_Miss",
        ("wncaab", "elo", "mississippi_st"): "Mississippi_St",
        ("wncaab", "elo", "tennessee"): "Tennessee",
        ("wncaab", "elo", "south_carolina"): "South_Carolina",
        ("wncaab", "elo", "kentucky"): "Kentucky",
        ("wncaab", "elo", "georgia"): "Georgia",
        ("wncaab", "elo", "missouri"): "Missouri",
        ("wncaab", "elo", "texas_a&m"): "Texas_A&M",
    }

    @staticmethod
    def resolve(sport: str, source: str, name: str) -> str:
        """Return canonical name for a team/player.

        Args:
            sport: Sport identifier (e.g., 'nba', 'nhl')
            source: Data source ('kalshi', 'the_odds_api', 'elo')
            name: Raw team/player name from source

        Returns:
            Canonical name
        """
        if not name:
            return name

        key = (sport.lower(), source.lower(), name.lower())

        # 1. Try exact match from mappings
        if key in NamingResolver._mappings:
            return NamingResolver._mappings[key]

        # 2. Try to find name in any source for this sport (cross-source fallback)
        for (s, src, n), canonical in NamingResolver._mappings.items():
            if s == sport.lower() and n == name.lower():
                return canonical

        # 3. Try cross-sport fallback (e.g., use 'ncaab' mapping for 'wncaab')
        for (s, src, n), canonical in NamingResolver._mappings.items():
            if n == name.lower():
                return canonical

        # 4. Return input unchanged if no mapping exists
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
