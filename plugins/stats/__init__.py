"""
plugins/stats — box-score fetching and advanced-stats derivation.

Each sport exposes a concrete ``BoxScoreFetcher`` sub-class that handles API
access, rate-limiting, and persistence to ``team_game_stats`` plus its
sport-specific extension table.  Advanced derived metrics live in
``advanced_stats``.

Exports
-------
BoxScoreFetcher        : abstract base class
NBABoxScoreFetcher     : NBA (nba_api)
NHLBoxScoreFetcher     : NHL (api-web.nhle.com)
MLBBoxScoreFetcher     : MLB (statsapi.mlb.com)
NFLBoxScoreFetcher     : NFL (nfl_data_py)
SoccerBoxScoreFetcher  : EPL + Ligue1 (football-data.co.uk / FBRef)
CBBBoxScoreFetcher     : NCAAB + WNCAAB (Massey Ratings / ESPN API)
TennisBoxScoreFetcher  : Tennis (Jeff Sackmann GitHub CSVs)
"""

from plugins.stats.base import BoxScoreFetcher
from plugins.stats.nba_box_score import NBABoxScoreFetcher
from plugins.stats.nhl_box_score import NHLBoxScoreFetcher
from plugins.stats.mlb_box_score import MLBBoxScoreFetcher
from plugins.stats.nfl_box_score import NFLBoxScoreFetcher
from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher
from plugins.stats.cbb_box_score import CBBBoxScoreFetcher
from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

__all__ = [
    "BoxScoreFetcher",
    "NBABoxScoreFetcher",
    "NHLBoxScoreFetcher",
    "MLBBoxScoreFetcher",
    "NFLBoxScoreFetcher",
    "SoccerBoxScoreFetcher",
    "CBBBoxScoreFetcher",
    "TennisBoxScoreFetcher",
]
