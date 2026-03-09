from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NamingContext:
    """Context for resolving a team or player name."""

    sport: str
    source: str
    name: str

    def to_key(self) -> tuple:
        """Return the lookup key for this context."""
        return (self.sport.lower(), self.source.lower(), self.name.lower())


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
        # NHL
        ("nhl", "kalshi", "ana"): "ANA",
        ("nhl", "kalshi", "ari"): "ARI",
        ("nhl", "kalshi", "bos"): "BOS",
        ("nhl", "kalshi", "buf"): "BUF",
        ("nhl", "kalshi", "cgy"): "CGY",
        ("nhl", "kalshi", "car"): "CAR",
        ("nhl", "kalshi", "chi"): "CHI",
        ("nhl", "kalshi", "col"): "COL",
        ("nhl", "kalshi", "cbj"): "CBJ",
        ("nhl", "kalshi", "dal"): "DAL",
        ("nhl", "kalshi", "det"): "DET",
        ("nhl", "kalshi", "edm"): "EDM",
        ("nhl", "kalshi", "fla"): "FLA",
        ("nhl", "kalshi", "lak"): "LAK",
        ("nhl", "kalshi", "min"): "MIN",
        ("nhl", "kalshi", "mtl"): "MTL",
        ("nhl", "kalshi", "nsh"): "NSH",
        ("nhl", "kalshi", "njd"): "NJD",
        ("nhl", "kalshi", "nyi"): "NYI",
        ("nhl", "kalshi", "nyr"): "NYR",
        ("nhl", "kalshi", "ott"): "OTT",
        ("nhl", "kalshi", "phi"): "PHI",
        ("nhl", "kalshi", "pit"): "PIT",
        ("nhl", "kalshi", "sjs"): "SJS",
        ("nhl", "kalshi", "sea"): "SEA",
        ("nhl", "kalshi", "stl"): "STL",
        ("nhl", "kalshi", "tbl"): "TBL",
        ("nhl", "kalshi", "tor"): "TOR",
        ("nhl", "kalshi", "uta"): "UTA",
        ("nhl", "kalshi", "van"): "VAN",
        ("nhl", "kalshi", "vgk"): "VGK",
        ("nhl", "kalshi", "wsh"): "WSH",
        ("nhl", "kalshi", "wpg"): "WPG",
        # NHL ELO / Canonical Mappings
        ("nhl", "elo", "anaheim ducks"): "ANA",
        ("nhl", "elo", "anaheim"): "ANA",
        ("nhl", "elo", "arizona coyotes"): "ARI",
        ("nhl", "elo", "arizona"): "ARI",
        ("nhl", "elo", "boston bruins"): "BOS",
        ("nhl", "elo", "boston"): "BOS",
        ("nhl", "elo", "buffalo sabres"): "BUF",
        ("nhl", "elo", "buffalo"): "BUF",
        ("nhl", "elo", "calgary flames"): "CGY",
        ("nhl", "elo", "calgary"): "CGY",
        ("nhl", "elo", "carolina hurricanes"): "CAR",
        ("nhl", "elo", "carolina"): "CAR",
        ("nhl", "elo", "chicago blackhawks"): "CHI",
        ("nhl", "elo", "chicago"): "CHI",
        ("nhl", "elo", "colorado avalanche"): "COL",
        ("nhl", "elo", "colorado"): "COL",
        ("nhl", "elo", "columbus blue jackets"): "CBJ",
        ("nhl", "elo", "columbus"): "CBJ",
        ("nhl", "elo", "dallas stars"): "DAL",
        ("nhl", "elo", "dallas"): "DAL",
        ("nhl", "elo", "detroit red wings"): "DET",
        ("nhl", "elo", "detroit"): "DET",
        ("nhl", "elo", "edmonton oilers"): "EDM",
        ("nhl", "elo", "edmonton"): "EDM",
        ("nhl", "elo", "florida panthers"): "FLA",
        ("nhl", "elo", "florida"): "FLA",
        ("nhl", "elo", "panthers"): "FLA",
        ("nhl", "elo", "los angeles kings"): "LAK",
        ("nhl", "elo", "los angeles"): "LAK",
        ("nhl", "elo", "losangeles"): "LAK",
        ("nhl", "elo", "minnesota wild"): "MIN",
        ("nhl", "elo", "minnesota"): "MIN",
        ("nhl", "elo", "montreal canadiens"): "MTL",
        ("nhl", "elo", "montréal canadiens"): "MTL",
        ("nhl", "elo", "montreal"): "MTL",
        ("nhl", "elo", "nashville predators"): "NSH",
        ("nhl", "elo", "nashville"): "NSH",
        ("nhl", "elo", "new jersey devils"): "NJD",
        ("nhl", "elo", "new jersey"): "NJD",
        ("nhl", "elo", "newjersey"): "NJD",
        ("nhl", "elo", "new york islanders"): "NYI",
        ("nhl", "elo", "ny islanders"): "NYI",
        ("nhl", "elo", "nyislanders"): "NYI",
        ("nhl", "elo", "new york rangers"): "NYR",
        ("nhl", "elo", "ny rangers"): "NYR",
        ("nhl", "elo", "nyrangers"): "NYR",
        ("nhl", "elo", "ottawa senators"): "OTT",
        ("nhl", "elo", "ottawa"): "OTT",
        ("nhl", "elo", "philadelphia flyers"): "PHI",
        ("nhl", "elo", "philadelphia"): "PHI",
        ("nhl", "elo", "pittsburgh penguins"): "PIT",
        ("nhl", "elo", "pittsburgh"): "PIT",
        ("nhl", "elo", "san jose sharks"): "SJS",
        ("nhl", "elo", "san jose"): "SJS",
        ("nhl", "elo", "sanjose"): "SJS",
        ("nhl", "elo", "seattle kraken"): "SEA",
        ("nhl", "elo", "seattle"): "SEA",
        ("nhl", "elo", "seattlekraken"): "SEA",
        ("nhl", "elo", "st. louis blues"): "STL",
        ("nhl", "elo", "st. louis"): "STL",
        ("nhl", "elo", "st.louis"): "STL",
        ("nhl", "elo", "st louis blues"): "STL",
        ("nhl", "elo", "tampa bay lightning"): "TBL",
        ("nhl", "elo", "tampa bay"): "TBL",
        ("nhl", "elo", "tampabay"): "TBL",
        ("nhl", "elo", "toronto maple leafs"): "TOR",
        ("nhl", "elo", "toronto"): "TOR",
        ("nhl", "elo", "utah hockey club"): "UTA",
        ("nhl", "elo", "utah"): "UTA",
        ("nhl", "elo", "utah mammoth"): "UTA",
        ("nhl", "elo", "vancouver canucks"): "VAN",
        ("nhl", "elo", "vancouver"): "VAN",
        ("nhl", "elo", "vegas golden knights"): "VGK",
        ("nhl", "elo", "vegas"): "VGK",
        ("nhl", "elo", "washington capitals"): "WSH",
        ("nhl", "elo", "washington"): "WSH",
        ("nhl", "elo", "winnipeg jets"): "WPG",
        ("nhl", "elo", "winnipeg"): "WPG",
    }

    @staticmethod
    def resolve(context: NamingContext) -> str:
        """Return canonical name for a team/player using NamingContext.

        Args:
            context: NamingContext object containing sport, source, and name

        Returns:
            Canonical name or original name if no mapping exists
        """
        if not context.name:
            return context.name

        key = context.to_key()

        # 1. Try exact match from mappings
        if key in NamingResolver._mappings:
            return NamingResolver._mappings[key]

        # 2. Try to find name in any source for this sport (cross-source fallback)
        for (s, src, n), canonical in NamingResolver._mappings.items():
            if s == context.sport.lower() and n == context.name.lower():
                return canonical

        # 3. Try cross-sport fallback (e.g., use 'ncaab' mapping for 'wncaab')
        for (s, src, n), canonical in NamingResolver._mappings.items():
            if n == context.name.lower():
                return canonical

        # 4. Return input unchanged if no mapping exists
        return context.name

    @staticmethod
    def add_mapping(
        context: NamingContext,
        canonical_name: str,
    ) -> None:
        """Add a mapping from raw name to canonical name.

        Args:
            context: NamingContext object containing sport, source, and raw name
            canonical_name: Canonical/normalized name
        """
        if not context.sport or not context.source or not context.name:
            raise ValueError("NamingContext must have sport, source, and name.")

        key = context.to_key()
        NamingResolver._mappings[key] = canonical_name
