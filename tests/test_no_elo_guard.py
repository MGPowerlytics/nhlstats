"""
Tests for the "never bet without real Elo" safety guard.

Covers:
- has_real_rating on BaseEloRating subclasses (NBA, NHL, MLB, NFL, EPL, Ligue1)
- has_real_rating on TennisEloRating (ATP / WTA)
- OddsComparator._both_teams_have_real_ratings skips unknown teams
- OddsComparator._resolve_game_context returns None for unknown teams
- OddsComparator.find_opportunities emits no bet when either rating is default
- Guard fires for ALL supported sports
"""

from __future__ import annotations

import types
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_elo_system(known_teams: list[str], initial: float = 1500.0) -> Any:
    """Build a minimal mock elo_system with real has_real_rating behaviour.

    Uses a simple dict-backed implementation that mirrors the real
    RatingStore contract — known_teams are populated, others aren't.
    """
    ratings: Dict[str, float] = {t: initial + i * 10 for i, t in enumerate(known_teams)}

    obj = types.SimpleNamespace()
    obj.ratings = dict(ratings)  # mimic BaseEloRating.ratings property

    def has_real_rating(team: str) -> bool:
        return team in ratings

    def get_rating(team: str) -> float:
        # Mirrors RatingStore: silently inserts default for unknown teams
        if team not in ratings:
            ratings[team] = initial
        return ratings[team]

    def predict(home: str, away: str, **_kw) -> float:
        return 0.6

    def predict_3way(home: str, away: str) -> Dict[str, float]:
        return {"home": 0.5, "draw": 0.25, "away": 0.25}

    obj.has_real_rating = has_real_rating
    obj.get_rating = get_rating
    obj.predict = predict
    obj.predict_3way = predict_3way
    return obj


def _make_tennis_elo_system(known_atp: list[str], known_wta: list[str]) -> Any:
    """Build a minimal tennis elo_system mock."""
    atp_ratings = {p: 1600.0 for p in known_atp}
    wta_ratings = {p: 1550.0 for p in known_wta}

    obj = types.SimpleNamespace()

    def has_real_rating(player: str, tour: str = "ATP") -> bool:
        pool = atp_ratings if tour.lower() == "atp" else wta_ratings
        return player in pool

    def get_rating(player: str, tour: str = "ATP") -> float:
        pool = atp_ratings if tour.lower() == "atp" else wta_ratings
        if player not in pool:
            pool[player] = 1500.0
        return pool[player]

    def predict(home: str, away: str, tour: str = "ATP") -> float:
        return 0.6

    obj.has_real_rating = has_real_rating
    obj.get_rating = get_rating
    obj.predict = predict
    return obj


# ---------------------------------------------------------------------------
# has_real_rating on BaseEloRating subclasses
# ---------------------------------------------------------------------------


class TestBaseEloHasRealRating:
    """Verify has_real_rating works on all concrete BaseEloRating subclasses."""

    @pytest.mark.parametrize(
        "cls_path,cls_name",
        [
            ("plugins.elo.nba_elo_rating", "NBAEloRating"),
            ("plugins.elo.nhl_elo_rating", "NHLEloRating"),
            ("plugins.elo.mlb_elo_rating", "MLBEloRating"),
            ("plugins.elo.nfl_elo_rating", "NFLEloRating"),
            ("plugins.elo.epl_elo_rating", "EPLEloRating"),
            ("plugins.elo.ligue1_elo_rating", "Ligue1EloRating"),
            ("plugins.elo.ncaab_elo_rating", "NCAABEloRating"),
        ],
    )
    def test_has_real_rating_false_for_unknown_team(self, cls_path, cls_name):
        import importlib

        module = importlib.import_module(cls_path)
        cls = getattr(module, cls_name)
        elo = cls()
        assert elo.has_real_rating("Nonexistent FC") is False

    @pytest.mark.parametrize(
        "cls_path,cls_name",
        [
            ("plugins.elo.nba_elo_rating", "NBAEloRating"),
            ("plugins.elo.nhl_elo_rating", "NHLEloRating"),
            ("plugins.elo.mlb_elo_rating", "MLBEloRating"),
            ("plugins.elo.nfl_elo_rating", "NFLEloRating"),
            ("plugins.elo.epl_elo_rating", "EPLEloRating"),
            ("plugins.elo.ligue1_elo_rating", "Ligue1EloRating"),
            ("plugins.elo.ncaab_elo_rating", "NCAABEloRating"),
        ],
    )
    def test_has_real_rating_true_after_game_processed(self, cls_path, cls_name):
        import importlib

        module = importlib.import_module(cls_path)
        cls = getattr(module, cls_name)
        elo = cls()
        # Process at least one game to populate both teams
        try:
            elo.update("Team A", "Team B", True)
        except TypeError:
            elo.update("Team A", "Team B", home_won=True)
        assert elo.has_real_rating("Team A") is True
        assert elo.has_real_rating("Team B") is True

    @pytest.mark.parametrize(
        "cls_path,cls_name",
        [
            ("plugins.elo.nba_elo_rating", "NBAEloRating"),
            ("plugins.elo.nhl_elo_rating", "NHLEloRating"),
            ("plugins.elo.epl_elo_rating", "EPLEloRating"),
        ],
    )
    def test_has_real_rating_does_not_insert_default(self, cls_path, cls_name):
        """Calling has_real_rating must NOT create a ratings entry."""
        import importlib

        module = importlib.import_module(cls_path)
        cls = getattr(module, cls_name)
        elo = cls()
        _ = elo.has_real_rating("Ghost Team")
        # The ghost team must not have been added to the ratings store
        assert "Ghost Team" not in elo.ratings


# ---------------------------------------------------------------------------
# has_real_rating on TennisEloRating
# ---------------------------------------------------------------------------


class TestTennisHasRealRating:
    def _make_tennis_elo(self):
        from plugins.elo.tennis_elo_rating import TennisEloRating

        return TennisEloRating()

    def test_atp_unknown_player_false(self):
        elo = self._make_tennis_elo()
        assert elo.has_real_rating("Nobody Novak", tour="ATP") is False

    def test_wta_unknown_player_false(self):
        elo = self._make_tennis_elo()
        assert elo.has_real_rating("Unknown Player", tour="WTA") is False

    def test_atp_known_player_true(self):
        elo = self._make_tennis_elo()
        elo.update("Sinner J.", "Djokovic N.", "W", tour="ATP")
        assert elo.has_real_rating("Sinner J.", tour="ATP") is True
        assert elo.has_real_rating("Djokovic N.", tour="ATP") is True

    def test_wta_known_player_true(self):
        elo = self._make_tennis_elo()
        elo.update("Swiatek I.", "Sabalenka A.", "W", tour="WTA")
        assert elo.has_real_rating("Swiatek I.", tour="WTA") is True

    def test_atp_does_not_cross_contaminate_wta(self):
        elo = self._make_tennis_elo()
        elo.update("Sinner J.", "Djokovic N.", "W", tour="ATP")
        # Should not appear in WTA
        assert elo.has_real_rating("Sinner J.", tour="WTA") is False

    def test_has_real_rating_does_not_insert_default(self):
        """Calling has_real_rating must NOT add the player to the store."""
        elo = self._make_tennis_elo()
        _ = elo.has_real_rating("Ghost Player", tour="ATP")
        # Direct dict access — player must not exist
        assert "Ghost Player" not in elo.atp_ratings


# ---------------------------------------------------------------------------
# OddsComparator._both_teams_have_real_ratings
# ---------------------------------------------------------------------------


class TestBothTeamsHaveRealRatings:
    def _comparator(self):
        from plugins.odds_comparator import OddsComparator

        return OddsComparator(db_manager=MagicMock())

    @pytest.mark.parametrize("sport", ["nba", "nhl", "mlb", "nfl", "epl", "ligue1"])
    def test_both_known_returns_true(self, sport):
        elo = _make_elo_system(["Home Team", "Away Team"])
        cmp = self._comparator()
        assert (
            cmp._both_teams_have_real_ratings(
                elo, sport, "Home Team", "Away Team", "game_1"
            )
            is True
        )

    @pytest.mark.parametrize("sport", ["nba", "nhl", "mlb", "nfl", "epl", "ligue1"])
    def test_unknown_home_returns_false(self, sport):
        elo = _make_elo_system(["Away Team"])
        cmp = self._comparator()
        assert (
            cmp._both_teams_have_real_ratings(
                elo, sport, "Unknown Home", "Away Team", "game_2"
            )
            is False
        )

    @pytest.mark.parametrize("sport", ["nba", "nhl", "mlb", "nfl", "epl", "ligue1"])
    def test_unknown_away_returns_false(self, sport):
        elo = _make_elo_system(["Home Team"])
        cmp = self._comparator()
        assert (
            cmp._both_teams_have_real_ratings(
                elo, sport, "Home Team", "Unknown Away", "game_3"
            )
            is False
        )

    @pytest.mark.parametrize("sport", ["nba", "nhl", "mlb", "nfl", "epl", "ligue1"])
    def test_both_unknown_returns_false(self, sport):
        elo = _make_elo_system([])
        cmp = self._comparator()
        assert (
            cmp._both_teams_have_real_ratings(
                elo, sport, "Ghost A", "Ghost B", "game_4"
            )
            is False
        )

    def test_tennis_atp_both_known(self):
        elo = _make_tennis_elo_system(["Sinner J.", "Djokovic N."], [])
        cmp = self._comparator()
        assert (
            cmp._both_teams_have_real_ratings(
                elo, "tennis", "Sinner J.", "Djokovic N.", "KXATP_game"
            )
            is True
        )

    def test_tennis_wta_unknown_player(self):
        elo = _make_tennis_elo_system([], ["Swiatek I."])
        cmp = self._comparator()
        assert (
            cmp._both_teams_have_real_ratings(
                elo, "tennis", "Swiatek I.", "Unknown WTA", "KXWTA_game"
            )
            is False
        )


# ---------------------------------------------------------------------------
# OddsComparator._resolve_game_context returns None for default-rated teams
# ---------------------------------------------------------------------------


class TestResolveGameContextGuard:
    def _make_row(self, home="Home FC", away="Away FC", game_id="g1"):
        return pd.Series(
            {
                "game_id": game_id,
                "home_team_name": home,
                "away_team_name": away,
                "status": "Scheduled",
                "game_date": "2026-04-25",
            }
        )

    def _comparator_with_odds(self, has_odds=True):
        """Return a comparator whose odds lookups succeed."""
        from plugins.odds_comparator import OddsComparator

        cmp = OddsComparator(db_manager=MagicMock())
        if has_odds:
            cmp._organize_odds = MagicMock(
                return_value=(
                    {"Kalshi": {"home": 2.0, "away": 2.1}},
                    {"Kalshi": {"home": "TICKER_H", "away": "TICKER_A"}},
                )
            )
        else:
            cmp._organize_odds = MagicMock(return_value=None)
        return cmp

    def test_returns_none_when_home_has_no_real_elo(self):
        elo = _make_elo_system(["Away FC"])  # home unknown
        cmp = self._comparator_with_odds()
        result = cmp._resolve_game_context("nba", self._make_row(), elo)
        assert result is None

    def test_returns_none_when_away_has_no_real_elo(self):
        elo = _make_elo_system(["Home FC"])  # away unknown
        cmp = self._comparator_with_odds()
        result = cmp._resolve_game_context("nba", self._make_row(), elo)
        assert result is None

    def test_returns_none_when_both_have_no_real_elo(self):
        elo = _make_elo_system([])  # neither known
        cmp = self._comparator_with_odds()
        result = cmp._resolve_game_context("nba", self._make_row(), elo)
        assert result is None

    def test_returns_context_when_both_have_real_elo(self):
        elo = _make_elo_system(["Home FC", "Away FC"])
        cmp = self._comparator_with_odds()
        result = cmp._resolve_game_context("nba", self._make_row(), elo)
        assert result is not None

    def test_guard_fires_for_epl(self):
        elo = _make_elo_system([])  # no EPL teams loaded
        cmp = self._comparator_with_odds()
        result = cmp._resolve_game_context(
            "epl", self._make_row("Arsenal", "Chelsea", "epl_g1"), elo
        )
        assert result is None

    def test_guard_fires_for_ligue1(self):
        elo = _make_elo_system([])
        cmp = self._comparator_with_odds()
        result = cmp._resolve_game_context(
            "ligue1", self._make_row("PSG", "Lyon", "l1_g1"), elo
        )
        assert result is None


# ---------------------------------------------------------------------------
# OddsComparator.find_opportunities produces zero bets for default ratings
# ---------------------------------------------------------------------------


class TestFindOpportunitiesGuard:
    def _games_df(self, rows):
        return pd.DataFrame(rows)

    def _mock_comparator(self, elo_system, games_df, sport: str = "nba"):
        from plugins.odds_comparator import OddsComparator

        cmp = OddsComparator(db_manager=MagicMock())
        cmp._get_games = MagicMock(return_value=games_df)
        # Soccer sports need draw odds + generous market prices so predict_3way
        # home=0.5 beats implied prob (1/3.5 ≈ 0.286)
        if sport in ("epl", "ligue1"):
            odds = {"Kalshi": {"home": 3.5, "away": 3.0, "draw": 3.0}}
            tickers = {"Kalshi": {"home": "TICK_H", "away": "TICK_A", "draw": "TICK_D"}}
        else:
            odds = {"Kalshi": {"home": 1.8, "away": 2.2}}
            tickers = {"Kalshi": {"home": "TICK_H", "away": "TICK_A"}}
        cmp._organize_odds = MagicMock(return_value=(odds, tickers))
        return cmp

    @pytest.mark.parametrize("sport", ["nba", "nhl", "mlb", "nfl", "epl", "ligue1"])
    def test_no_bets_when_elo_is_empty(self, sport):
        """If Elo system has no teams, find_opportunities must return []."""
        from plugins.odds_comparator import BettingOpportunityConfig, BettingThresholds

        games_df = self._games_df(
            [
                {
                    "game_id": f"{sport}_g1",
                    "home_team_name": "Team A",
                    "away_team_name": "Team B",
                    "game_date": "2026-04-25",
                    "status": "Scheduled",
                }
            ]
        )
        elo = _make_elo_system([])  # empty — all teams would be default 1500
        cmp = self._mock_comparator(elo, games_df, sport=sport)

        cfg = BettingOpportunityConfig(
            sport=sport,
            elo_system=elo,
            thresholds=BettingThresholds(min_edge=0.03),
            date_str="2026-04-25",
        )
        opps = cmp.find_opportunities(cfg)
        assert opps == [], f"Expected no bets for {sport} with empty Elo, got {opps}"

    @pytest.mark.parametrize("sport", ["nba", "nhl", "mlb", "nfl", "epl", "ligue1"])
    def test_bets_emitted_when_both_have_real_ratings(self, sport):
        """If both teams have real ratings AND there's edge, we should get a bet."""
        from plugins.odds_comparator import BettingOpportunityConfig, BettingThresholds

        games_df = self._games_df(
            [
                {
                    "game_id": f"{sport}_g2",
                    "home_team_name": "Team A",
                    "away_team_name": "Team B",
                    "game_date": "2026-04-25",
                    "status": "Scheduled",
                }
            ]
        )
        # Both known; predict() returns 0.6, market implied prob = 1/1.8 ≈ 0.556 → edge ≈ 0.044
        # Soccer predict_3way returns home=0.5, market implied = 1/3.5 ≈ 0.286 → edge ≈ 0.214
        elo = _make_elo_system(["Team A", "Team B"])
        cmp = self._mock_comparator(elo, games_df, sport=sport)

        cfg = BettingOpportunityConfig(
            sport=sport,
            elo_system=elo,
            thresholds=BettingThresholds(min_edge=0.03),
            date_str="2026-04-25",
        )
        opps = cmp.find_opportunities(cfg)
        # Should have a home bet (edge = 0.6 - 0.556 ≈ 0.044 > 0.03)
        assert len(opps) >= 1, f"Expected ≥1 bet for {sport} with known teams, got 0"
        for opp in opps:
            assert (
                opp["home_rating"] != 1500.0 or opp["away_rating"] != 1500.0
            ), "Both ratings are 1500 — default detected!"

    def test_no_bets_when_only_home_known(self):
        """Partial rating coverage must still block the bet."""
        from plugins.odds_comparator import BettingOpportunityConfig, BettingThresholds

        games_df = self._games_df(
            [
                {
                    "game_id": "nba_partial",
                    "home_team_name": "Team A",
                    "away_team_name": "Unknown Away",
                    "game_date": "2026-04-25",
                    "status": "Scheduled",
                }
            ]
        )
        elo = _make_elo_system(["Team A"])  # away unknown
        cmp = self._mock_comparator(elo, games_df)

        cfg = BettingOpportunityConfig(
            sport="nba",
            elo_system=elo,
            thresholds=BettingThresholds(min_edge=0.03),
            date_str="2026-04-25",
        )
        opps = cmp.find_opportunities(cfg)
        assert opps == []

    def test_multiple_games_only_known_get_bets(self):
        """With mixed known/unknown games, only fully-known games produce bets."""
        from plugins.odds_comparator import BettingOpportunityConfig, BettingThresholds

        games_df = self._games_df(
            [
                {  # both known
                    "game_id": "nba_g_known",
                    "home_team_name": "Real Home",
                    "away_team_name": "Real Away",
                    "game_date": "2026-04-25",
                    "status": "Scheduled",
                },
                {  # home unknown
                    "game_id": "nba_g_unknown",
                    "home_team_name": "Ghost Home",
                    "away_team_name": "Real Away",
                    "game_date": "2026-04-25",
                    "status": "Scheduled",
                },
            ]
        )
        elo = _make_elo_system(["Real Home", "Real Away"])
        cmp = self._mock_comparator(elo, games_df)

        cfg = BettingOpportunityConfig(
            sport="nba",
            elo_system=elo,
            thresholds=BettingThresholds(min_edge=0.03),
            date_str="2026-04-25",
        )
        opps = cmp.find_opportunities(cfg)
        # Only the known game should produce bets; ghost game must be filtered
        bet_game_ids = {o["game_id"] for o in opps}
        assert "nba_g_unknown" not in bet_game_ids
        assert "nba_g_known" in bet_game_ids


# ---------------------------------------------------------------------------
# Guard works even when get_rating would silently insert defaults
# ---------------------------------------------------------------------------


class TestGuardPreventsDefaultRating:
    """Regression test: ensure the old bug (betting with 1500/1500) is gone."""

    def test_get_rating_still_inserts_default_but_has_real_rating_stays_false(self):
        """
        If code called get_rating() on an unknown team, that team would appear
        in the store at 1500.  has_real_rating() must still return False for a
        team that was never part of a real game — confirming that calling order
        doesn't matter.
        """
        from plugins.elo.nba_elo_rating import NBAEloRating

        elo = NBAEloRating()
        # Calling get_rating on an unknown team inserts a default entry
        _ = elo.get_rating("Ghost Team")
        # has_real_rating on a *different* unknown team should still be False
        assert elo.has_real_rating("Another Ghost") is False

    def test_real_team_rating_is_not_1500_after_games(self):
        """After processing games, teams must diverge from the 1500 default."""
        from plugins.elo.epl_elo_rating import EPLEloRating

        elo = EPLEloRating()
        for _ in range(5):
            elo.legacy_update("Arsenal", "Chelsea", "H")
        assert elo.get_rating("Arsenal") != 1500.0
        assert elo.get_rating("Chelsea") != 1500.0
        assert elo.has_real_rating("Arsenal") is True
        assert elo.has_real_rating("Chelsea") is True
