"""Tests for calibrated tennis probabilities at the betting boundary."""

from __future__ import annotations

import pytest

from plugins.elo import TennisEloRating
from plugins.odds_comparator import GameContext, OddsComparator


class _CalibratedTennisStub:
    """Minimal tennis model exposing both raw and calibrated prediction APIs."""

    def get_rating(self, player: str, tour: str | None = None) -> float:
        return {"Player A": 1600.0, "Player B": 1500.0}[player]

    def predict(self, player_a: str, player_b: str, *, tour: str) -> float:
        return 0.61

    def predict_with_payload(self, player_a: str, player_b: str, tour: str) -> dict:
        return {
            "player_a": player_a,
            "player_b": player_b,
            "tour": tour.upper(),
            "raw_prob_a": 0.61,
            "calibrated_prob_a": 0.57,
        }


class _SurfaceLookupDB:
    """Small DB stub for tennis surface inference."""

    def fetch_df(self, query: str, params: dict | None = None):  # type: ignore[override]
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "game_date": "2026-05-08",
                    "surface": "Clay",
                    "winner": "Player A",
                    "loser": "Opponent C",
                },
                {
                    "game_date": "2026-05-07",
                    "surface": "Clay",
                    "winner": "Player B",
                    "loser": "Opponent D",
                },
                {
                    "game_date": "2026-04-20",
                    "surface": "Hard",
                    "winner": "Player A",
                    "loser": "Player B",
                },
            ]
        )


class _TourAwareRealRatingStub:
    """Rating guard stub that records which tour was queried."""

    def __init__(self, valid_tour: str) -> None:
        self.valid_tour = valid_tour.upper()
        self.queries: list[tuple[str, str]] = []

    def has_real_rating(self, player: str, tour: str = "ATP") -> bool:
        normalized_tour = tour.upper()
        self.queries.append((player, normalized_tour))
        return normalized_tour == self.valid_tour


def test_tennis_betting_uses_calibrated_probability_when_available() -> None:
    """OddsComparator should evaluate tennis bets using calibrated probability."""
    context = GameContext(
        sport="tennis",
        game_id="TENNIS_ATP_2026-05-10_PlayerA_PlayerB",
        home_team_name="Player A",
        away_team_name="Player B",
        source="kalshi",
        canon_home="Player A",
        canon_away="Player B",
        elo_home="Player A",
        elo_away="Player B",
        odds_by_bm={"Kalshi": {"home": 2.0, "away": 2.0}},
        tickers_by_bm={
            "Kalshi": {
                "home": "KXATPMATCH-26MAY10PA-PB",
                "away": "KXATPMATCH-26MAY10PA-PB",
            }
        },
        elo_system=_CalibratedTennisStub(),
    )

    assert context.calculate_probabilities()

    assert context.home_win_prob == 0.57
    assert context.away_win_prob == pytest.approx(0.43)
    assert context.tour == "ATP"


def test_tennis_real_rating_guard_uses_kalshi_ticker_for_tour() -> None:
    """Generic game IDs must not force ATP players through WTA ratings."""
    comparator = OddsComparator()
    elo = _TourAwareRealRatingStub(valid_tour="ATP")

    assert comparator._both_teams_have_real_ratings(
        elo_system=elo,
        sport="tennis",
        elo_home="Player A",
        elo_away="Player B",
        game_id="unified_game_without_tour_marker",
        tickers_by_bm={
            "Kalshi": {
                "home": "KXATPMATCH-26MAY10PA-PB",
                "away": "KXATPMATCH-26MAY10PA-PB",
            }
        },
    )

    assert elo.queries == [("Player A", "ATP"), ("Player B", "ATP")]


def test_tennis_elo_exposes_match_count_without_mutating_unknown_players() -> None:
    """get_match_count should report played matches and keep unknown players at zero."""
    elo = TennisEloRating()

    assert elo.get_match_count("Player A", "ATP") == 0
    elo.update("Player A", "Player B", tour="ATP")

    assert elo.get_match_count("Player A", "ATP") == 1
    assert elo.get_match_count("Player B", "ATP") == 1
    assert elo.get_match_count("Unknown Player", "ATP") == 0


def test_tennis_probability_model_uses_inferred_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upcoming tennis scoring should use inferred surface instead of hard-coding Hard."""
    captured: dict[str, object] = {}

    def fake_predict_with_artifact(**kwargs):
        captured.update(kwargs)
        from plugins.elo.tennis_probability_model import TennisProbabilityResult

        return TennisProbabilityResult(
            prob_a=0.59,
            source="ensemble",
            calibrated_elo_prob_a=0.57,
            feature_model_prob_a=0.60,
            model_version="tennis_probability_model_v2",
            data_certainty=0.75,
        )

    class _ExistingModelPath:
        def exists(self) -> bool:
            return True

    monkeypatch.setattr(
        "plugins.elo.tennis_probability_model.DEFAULT_MODEL_PATH",
        _ExistingModelPath(),
    )
    monkeypatch.setattr(
        "plugins.elo.tennis_probability_model.predict_with_artifact",
        fake_predict_with_artifact,
    )
    monkeypatch.setattr(
        "plugins.odds_comparator._load_tennis_probability_history",
        lambda: __import__("pandas").DataFrame(
            [{"winner": "Player A", "loser": "Player B"}]
        ),
    )

    comparator = OddsComparator(db_manager=_SurfaceLookupDB())
    context = GameContext(
        sport="tennis",
        game_id="TENNIS_ATP_2026-05-10_PlayerA_PlayerB",
        home_team_name="Player A",
        away_team_name="Player B",
        source="kalshi",
        canon_home="Player A",
        canon_away="Player B",
        elo_home="Player A",
        elo_away="Player B",
        odds_by_bm={"Kalshi": {"home": 2.0, "away": 2.0}},
        tickers_by_bm={
            "Kalshi": {
                "home": "KXATPMATCH-26MAY10PA-PB",
                "away": "KXATPMATCH-26MAY10PA-PB",
            }
        },
        elo_system=_CalibratedTennisStub(),
        surface=comparator._infer_tennis_surface(
            player_a="Player A",
            player_b="Player B",
            as_of_date="2026-05-10",
        ),
    )

    assert context.calculate_probabilities()
    assert context.home_win_prob == pytest.approx(0.59)
    assert captured["surface"] == "Clay"
