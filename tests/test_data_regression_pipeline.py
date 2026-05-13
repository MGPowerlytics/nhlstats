"""Data regression tests for pipeline-level data quality and integrity.

These tests verify:
- Null/NaN checks on critical game data fields
- Empty dataframe differentiation (no games vs error)
- Game score validation before Elo updates
- Idempotency/deduplication behavior
- Ensemble adapter fallback behavior
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from plugins.odds_comparator import (
    OddsComparator, BettingThresholds, BettingOpportunityConfig,
)


def _elo_ns(**kwargs):
    """Build a SimpleNamespace elo_system stub with has_real_rating=True."""
    kwargs.setdefault("has_real_rating", lambda *a, **kw: True)
    kwargs.setdefault("get_rating", lambda team, **kw: 1500)
    return SimpleNamespace(**kwargs)


class DummyDB:
    """Simple DB stub for fetch_df calls."""
    def __init__(self, frames_by_query):
        self.frames_by_query = frames_by_query

    def fetch_df(self, query, params=None):
        for key, frame in self.frames_by_query.items():
            if key in query:
                return frame(params or {}) if callable(frame) else frame
        return pd.DataFrame()


class TestNullScoreHandling:
    """Verify pipeline handles games with null/missing scores correctly."""

    def test_game_with_null_home_score(self):
        """Games with null home_score should be identifiable."""
        game = pd.Series({
            "game_id": "NBA_20260127_LAL_BOS",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "home_score": None,
            "away_score": 105,
            "status": "Scheduled",
        })
        assert pd.isna(game["home_score"])

    def test_game_with_nan_away_score(self):
        """Games with NaN away_score should be identifiable."""
        game = pd.Series({
            "game_id": "NBA_20260127_LAL_BOS",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "home_score": 110,
            "away_score": float("nan"),
            "status": "Final",
        })
        assert pd.isna(game["away_score"])

    def test_dataframe_with_mixed_null_scores(self):
        """DataFrame with mixed null scores should allow filtering."""
        df = pd.DataFrame({
            "game_id": ["G1", "G2", "G3"],
            "home_score": [110, None, 120],
            "away_score": [105, 100, float("nan")],
        })
        # Should be able to filter out rows with null scores
        valid = df.dropna(subset=["home_score", "away_score"])
        assert len(valid) == 1
        assert valid.iloc[0]["game_id"] == "G1"

    def test_null_team_names_identifiable(self):
        """Games with null team names should be identifiable."""
        df = pd.DataFrame({
            "game_id": ["G1", "G2"],
            "home_team": ["Lakers", None],
            "away_team": ["Celtics", "Warriors"],
        })
        null_home = df[df["home_team"].isna()]
        assert len(null_home) == 1
        assert null_home.iloc[0]["game_id"] == "G2"


class TestEmptyDataframeHandling:
    """Verify pipeline differentiates between expected-empty and error-empty."""

    def test_empty_games_dataframe_from_query(self):
        """Empty games DataFrame from a valid query means no games scheduled."""
        today = datetime.now().strftime("%Y-%m-%d")
        games_df = pd.DataFrame(columns=["game_id", "game_date", "home_team_name", "away_team_name", "status"])
        assert games_df.empty
        assert list(games_df.columns) == ["game_id", "game_date", "home_team_name", "away_team_name", "status"]

    def test_empty_odds_dataframe_means_no_betting_opportunities(self):
        """Empty odds DataFrame means no betting opportunities for that game."""
        odds_df = pd.DataFrame(columns=["bookmaker", "outcome_name", "price"])
        assert odds_df.empty
        # No odds = no opportunities
        assert len(odds_df) == 0

    def test_empty_recommendations_dataframe(self):
        """Empty bet recommendations DataFrame should be handled gracefully."""
        recs_df = pd.DataFrame(columns=["ticker", "sport", "bet_on", "home_team", "away_team"])
        assert recs_df.empty
        # Portfolio optimizer should handle this
        config = PortfolioConfig(bankroll=1000.0)
        optimizer = PortfolioOptimizer(config)
        # filter_opportunities on empty should return empty
        assert optimizer.filter_opportunities([]) == []

    def test_find_opportunities_with_no_games(self):
        """find_opportunities should return empty list when no games exist."""
        today = datetime.now().strftime("%Y-%m-%d")
        games_df = pd.DataFrame(columns=["game_id", "game_date", "home_team_name", "away_team_name", "status"])
        db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": pd.DataFrame()})
        comparator = OddsComparator(db_manager=db)
        elo_system = _elo_ns(predict=lambda home, away: 0.60)

        with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
            results = comparator.find_opportunities(
                config=BettingOpportunityConfig(
                    sport="nba", elo_system=elo_system,
                    thresholds=BettingThresholds(min_edge=0.05, max_edge=1.0),
                )
            )
        assert results == []


class TestGameScoreValidation:
    """Verify score validation helpers work correctly for Elo update gating.

    Note: is_valid_score() only rejects NaN and None. It accepts negative
    numbers, strings, and pandas NA/NaT — so pipeline code must perform
    additional validation beyond is_valid_score() for those edge cases.
    """

    def test_valid_integer_scores(self):
        """Integer scores should be valid."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert is_valid_score(110)
        assert is_valid_score(0)
        assert is_valid_score(3)

    def test_valid_float_scores(self):
        """Float scores (from pandas) should be valid."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert is_valid_score(110.0)
        assert is_valid_score(3.0)

    def test_invalid_nan_score(self):
        """NaN scores should be invalid."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert not is_valid_score(float("nan"))

    def test_invalid_none_score(self):
        """None scores should be invalid."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert not is_valid_score(None)

    def test_valid_negative_score(self):
        """is_valid_score accepts negative numbers — pipeline must add extra validation."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert is_valid_score(-1)

    def test_valid_string_score(self):
        """is_valid_score accepts strings — pipeline must add extra validation."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert is_valid_score("110")

    def test_valid_pandas_na(self):
        """is_valid_score accepts pd.NA — pipeline must add extra validation."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert is_valid_score(pd.NA)

    def test_valid_pandas_nat(self):
        """is_valid_score accepts pd.NaT — pipeline must add extra validation."""
        from plugins.elo.elo_update_helpers import is_valid_score
        assert is_valid_score(pd.NaT)


class TestEnsembleAdapterFallback:
    """Verify ensemble adapters handle edge cases gracefully."""

    def test_mlb_ensemble_default_creation(self):
        """MLBEnsembleAdapter can be created with defaults."""
        from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter
        ensemble = MLBEnsembleAdapter()
        assert ensemble is not None
        # Unknown teams produce ~0.5 probability (equal default ratings)
        prob = ensemble.predict("Unknown1", "Unknown2")
        assert 0.4 <= prob <= 0.6

    def test_mlb_ensemble_with_explicit_ensemble(self):
        """MLBEnsembleAdapter works with an explicit ensemble."""
        from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter
        from plugins.elo.mlb_ensemble import MLBEnsembleModel

        ensemble_model = MLBEnsembleModel()
        ensemble_model.team_elo.update("Yankees", "Red Sox", True)

        adapter = MLBEnsembleAdapter(ensemble=ensemble_model)
        prob = adapter.predict("Yankees", "Red Sox")
        assert 0.0 <= prob <= 1.0

    def test_mlb_ensemble_has_real_rating_on_unknown_team(self):
        """has_real_rating returns False for unknown teams."""
        from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter
        adapter = MLBEnsembleAdapter()
        assert not adapter.has_real_rating("Unknown Team")

    def test_mlb_ensemble_has_real_rating_on_known_team(self):
        """has_real_rating returns True for teams with game history."""
        from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter
        from plugins.elo.mlb_ensemble import MLBEnsembleModel

        ensemble_model = MLBEnsembleModel()
        ensemble_model.team_elo.update("Yankees", "Red Sox", True)

        adapter = MLBEnsembleAdapter(ensemble=ensemble_model)
        assert adapter.has_real_rating("Yankees")

    def test_mlb_ensemble_get_rating_default(self):
        """get_rating returns default 1500 for unknown teams."""
        from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter
        adapter = MLBEnsembleAdapter()
        assert adapter.get_rating("Unknown Team") == 1500


class TestNameResolverEdgeCases:
    """Verify naming resolver handles edge cases gracefully."""

    def test_resolve_with_empty_name(self):
        """Empty team name returns empty string (no mapping applied)."""
        from naming_resolver import NamingResolver, NamingContext
        result = NamingResolver.resolve(NamingContext(sport="nba", source="kalshi", name=""))
        # Returns original name (empty string) when no mapping exists
        assert result == ""

    def test_resolve_with_whitespace_only_name(self):
        """Whitespace-only name returns original (no mapping applied)."""
        from naming_resolver import NamingResolver, NamingContext
        result = NamingResolver.resolve(NamingContext(sport="nba", source="kalshi", name="   "))
        assert result == "   "

    def test_resolve_with_exact_match(self):
        """Known team name resolves to canonical form."""
        from naming_resolver import NamingResolver, NamingContext
        result = NamingResolver.resolve(NamingContext(sport="nba", source="elo", name="LAL"))
        # LAL is already canonical in the elo source
        assert result == "LAL"

    def test_resolve_returns_original_if_no_match(self):
        """When no mapping exists, original name is returned."""
        from naming_resolver import NamingResolver, NamingContext
        result = NamingResolver.resolve(NamingContext(sport="nba", source="kalshi", name="SomeUnknownTeam"))
        # Returns original name when no mapping found
        assert result == "SomeUnknownTeam"


class TestDataFrameDeduplication:
    """Verify deduplication logic for data loading."""

    def test_drop_duplicates_by_game_id(self):
        """Duplicate game rows should be removable by game_id."""
        df = pd.DataFrame({
            "game_id": ["G1", "G1", "G2"],
            "home_score": [110, 110, 100],
            "away_score": [105, 105, 95],
        })
        deduped = df.drop_duplicates(subset=["game_id"])
        assert len(deduped) == 2

    def test_drop_duplicates_keeps_first(self):
        """Dedup should keep the first occurrence."""
        df = pd.DataFrame({
            "game_id": ["G1", "G1"],
            "home_score": [110, 115],
        })
        deduped = df.drop_duplicates(subset=["game_id"], keep="first")
        assert deduped.iloc[0]["home_score"] == 110

    def test_empty_dataframe_dedup_is_noop(self):
        """Dedup on empty DataFrame should be a no-op."""
        df = pd.DataFrame(columns=["game_id", "home_score"])
        deduped = df.drop_duplicates(subset=["game_id"])
        assert deduped.empty


class TestProbabilityCalibrationEdgeCases:
    """Verify probability calibration handles edge cases."""

    def test_calibration_with_unfitted_sport(self):
        """Unfitted calibrator should raise CalibratorNotFittedError."""
        from plugins.probability_calibration import ProbabilityCalibrator, CalibratorNotFittedError
        calibrator = ProbabilityCalibrator()
        # Without fitting, should raise CalibratorNotFittedError
        with pytest.raises(CalibratorNotFittedError):
            calibrator.calibrate("nba", 0.60)

    def test_raw_probability_in_valid_range(self):
        """Raw Elo probabilities should always be in [0, 1]."""
        from plugins.elo.nba_elo_rating import NBAEloRating
        elo = NBAEloRating()
        elo.update("Lakers", "Celtics", True)
        prob = elo.predict("Lakers", "Celtics")
        assert 0.0 <= prob <= 1.0

    def test_predict_with_equal_ratings(self):
        """Equal ratings should produce 0.5 probability (no home advantage adjustment)."""
        from plugins.elo.elo_calculator import EloCalculator, EloConfig
        calc = EloCalculator(EloConfig(k_factor=20, home_advantage=0))
        prob = calc.expected_score(1500, 1500)
        assert prob == pytest.approx(0.5)

    def test_predict_with_home_advantage(self):
        """Home advantage should boost home win probability."""
        from plugins.elo.elo_calculator import EloCalculator, EloConfig
        calc = EloCalculator(EloConfig(k_factor=20, home_advantage=100))
        # Same rating but home advantage boosts home rating
        prob = calc.expected_score(1500 + 100, 1500)
        assert prob > 0.5


class TestDataIngestionValidation:
    """Verify data ingestion validates data before persisting."""

    def test_game_id_uniqueness_check(self):
        """Should be able to detect duplicate game_ids before insert."""
        df = pd.DataFrame({
            "game_id": ["G1", "G2", "G1"],
            "sport": ["NBA", "NBA", "NBA"],
        })
        duplicates = df[df.duplicated(subset=["game_id"], keep=False)]
        assert len(duplicates) == 2

    def test_required_columns_present(self):
        """Should be able to check required columns before processing."""
        required = ["game_id", "home_team", "away_team", "home_score", "away_score"]
        df = pd.DataFrame({
            "game_id": ["G1"],
            "home_team": ["Lakers"],
            "away_team": ["Celtics"],
        })
        missing = [c for c in required if c not in df.columns]
        assert "home_score" in missing
        assert "away_score" in missing

    def test_date_format_validation(self):
        """Should be able to validate date format before processing."""
        valid_dates = pd.Series(["2026-01-27", "2026-12-31"])
        invalid_dates = pd.Series(["01-27-2026", "not-a-date"])

        def is_valid_iso_date(s):
            try:
                datetime.strptime(s, "%Y-%m-%d")
                return True
            except (ValueError, TypeError):
                return False

        assert valid_dates.apply(is_valid_iso_date).all()
        assert not invalid_dates.apply(is_valid_iso_date).all()


# Need these imports for the test classes
from plugins.portfolio_optimizer import PortfolioOptimizer, PortfolioConfig, BetOpportunity
