"""Tests for plugins.stats.ingestion_schema."""

from datetime import date, timedelta

import pandas as pd
import pytest

from plugins.stats.ingestion_schema import (
    IngestionValidationError,
    IngestionValidationResult,
    MLBStatsExtSchema,
    NHLStatsExtSchema,
    SoccerStatsExtSchema,
    TeamGameStatsSchema,
    validate_ingestion,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_nhl_rows():
    """Minimal valid NHL ingestion rows."""
    today = date.today()
    return [
        {
            "game_id": "2023020001",
            "sport": "NHL",
            "team": "BOS",
            "opponent": "TOR",
            "is_home": True,
            "game_date": today - timedelta(days=1),
            "season": "2023",
            "points_for": 4,
            "points_against": 2,
            "won": True,
            "margin": 2,
            "off_rating": None,
            "def_rating": None,
            "pace": None,
        },
        {
            "game_id": "2023020001",
            "sport": "NHL",
            "team": "TOR",
            "opponent": "BOS",
            "is_home": False,
            "game_date": today - timedelta(days=1),
            "season": "2023",
            "points_for": 2,
            "points_against": 4,
            "won": False,
            "margin": -2,
            "off_rating": None,
            "def_rating": None,
            "pace": None,
        },
    ]


# ---------------------------------------------------------------------------
# TeamGameStatsSchema — core contract
# ---------------------------------------------------------------------------

class TestTeamGameStatsSchema:
    """Validate the core ingestion schema contract."""

    def test_valid_rows_pass(self, valid_nhl_rows):
        df = pd.DataFrame(valid_nhl_rows)
        # Should not raise
        result = TeamGameStatsSchema.validate(df)
        assert len(result) == 2

    def test_null_game_id_rejected(self, valid_nhl_rows):
        valid_nhl_rows[0]["game_id"] = None
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):  # SchemaError or SchemaErrors
            TeamGameStatsSchema.validate(df)

    def test_null_team_rejected(self, valid_nhl_rows):
        valid_nhl_rows[0]["team"] = None
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_null_opponent_rejected(self, valid_nhl_rows):
        valid_nhl_rows[0]["opponent"] = None
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_null_sport_rejected(self, valid_nhl_rows):
        valid_nhl_rows[0]["sport"] = None
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_negative_score_rejected(self, valid_nhl_rows):
        valid_nhl_rows[0]["points_for"] = -1
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_unreasonable_score_rejected(self, valid_nhl_rows):
        """Scores > 200 are impossible in major sports."""
        valid_nhl_rows[0]["points_for"] = 250
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_future_game_date_rejected(self, valid_nhl_rows):
        valid_nhl_rows[0]["game_date"] = date.today() + timedelta(days=365)
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_inconsistent_won_flag_rejected(self, valid_nhl_rows):
        """won=True but points_for < points_against should fail."""
        valid_nhl_rows[0]["won"] = True
        valid_nhl_rows[0]["points_for"] = 2
        valid_nhl_rows[0]["points_against"] = 4
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_inconsistent_margin_rejected(self, valid_nhl_rows):
        """margin must equal points_for - points_against."""
        valid_nhl_rows[0]["margin"] = 99
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)

    def test_extra_column_rejected_strict(self, valid_nhl_rows):
        """Strict mode should reject undeclared columns."""
        valid_nhl_rows[0]["extra_col"] = "oops"
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(Exception):
            TeamGameStatsSchema.validate(df)


# ---------------------------------------------------------------------------
# NHL extension schema
# ---------------------------------------------------------------------------

class TestNHLStatsExtSchema:
    """Validate hockey-specific extension schema."""

    def test_valid_nhl_ext(self):
        df = pd.DataFrame([
            {
                "game_id": "2023020001",
                "team": "BOS",
                "shots": 35,
                "sog": 30,
                "hits": 22,
                "blocks": 15,
                "pim": 6,
                "faceoff_pct": 0.52,
                "pp_goals": 1,
                "pp_opportunities": 3,
                "pp_pct": 0.333,
                "pk_goals_against": 0,
                "pk_opportunities": 2,
                "pk_pct": 1.0,
                "shooting_pct": 0.133,
            }
        ])
        result = NHLStatsExtSchema.validate(df)
        assert len(result) == 1

    def test_pp_goals_cannot_exceed_opportunities(self):
        df = pd.DataFrame([
            {
                "game_id": "2023020001",
                "team": "BOS",
                "pp_goals": 5,
                "pp_opportunities": 3,
            }
        ])
        with pytest.raises(Exception):
            NHLStatsExtSchema.validate(df)

    def test_negative_shots_rejected(self):
        df = pd.DataFrame([
            {"game_id": "g1", "team": "BOS", "shots": -1}
        ])
        with pytest.raises(Exception):
            NHLStatsExtSchema.validate(df)


# ---------------------------------------------------------------------------
# MLB extension schema
# ---------------------------------------------------------------------------

class TestMLBStatsExtSchema:
    """Validate baseball-specific extension schema."""

    def test_valid_mlb_ext(self):
        df = pd.DataFrame([
            {
                "game_id": "745431",
                "team": "NYY",
                "hits": 10,
                "errors": 1,
                "lob": 7,
                "doubles": 2,
                "triples": 0,
                "home_runs": 2,
                "rbi": 6,
                "stolen_bases": 1,
                "strikeouts": 8,
                "walks": 3,
                "at_bats": 34,
                "obp": 0.350,
                "slg": 0.500,
                "ops": 0.850,
                "woba": 0.340,
                "era": 3.00,
            }
        ])
        result = MLBStatsExtSchema.validate(df)
        assert len(result) == 1

    def test_hit_types_cannot_exceed_total_hits(self):
        df = pd.DataFrame([
            {
                "game_id": "745431",
                "team": "NYY",
                "hits": 5,
                "doubles": 6,  # more doubles than total hits
            }
        ])
        with pytest.raises(Exception):
            MLBStatsExtSchema.validate(df)


# ---------------------------------------------------------------------------
# Soccer extension schema
# ---------------------------------------------------------------------------

class TestSoccerStatsExtSchema:
    """Validate soccer-specific extension schema."""

    def test_valid_soccer_ext(self):
        df = pd.DataFrame([
            {
                "game_id": "E0_20231028_ARS_CHE",
                "team": "Arsenal",
                "shots": 15,
                "shots_on_target": 6,
                "fouls": 10,
                "yellow_cards": 2,
                "red_cards": 0,
                "corners": 7,
                "xg": 1.8,
                "xga": 0.9,
            }
        ])
        result = SoccerStatsExtSchema.validate(df)
        assert len(result) == 1

    def test_sot_cannot_exceed_shots(self):
        df = pd.DataFrame([
            {
                "game_id": "E0_20231028_ARS_CHE",
                "team": "Arsenal",
                "shots": 5,
                "shots_on_target": 8,
            }
        ])
        with pytest.raises(Exception):
            SoccerStatsExtSchema.validate(df)

    def test_negative_cards_rejected(self):
        df = pd.DataFrame([
            {"game_id": "g1", "team": "ARS", "red_cards": -1}
        ])
        with pytest.raises(Exception):
            SoccerStatsExtSchema.validate(df)


# ---------------------------------------------------------------------------
# validate_ingestion — integration-level checks
# ---------------------------------------------------------------------------

class TestValidateIngestion:
    """Test the high-level validate_ingestion entry point."""

    def test_valid_ingestion_passes(self, valid_nhl_rows):
        df = pd.DataFrame(valid_nhl_rows)
        result = validate_ingestion(df, sport="NHL")
        assert result.passed is True
        assert result.row_count == 2
        assert result.sport == "NHL"
        assert result.errors == []

    def test_schema_violation_raises(self, valid_nhl_rows):
        valid_nhl_rows[0]["game_id"] = None
        df = pd.DataFrame(valid_nhl_rows)
        with pytest.raises(IngestionValidationError) as exc_info:
            validate_ingestion(df, sport="NHL")
        assert "game_id" in str(exc_info.value).lower()

    def test_drift_warning_on_mismatch(self, valid_nhl_rows):
        """When sport column doesn't match expected, warn but don't fail."""
        valid_nhl_rows[0]["sport"] = "NBA"
        valid_nhl_rows[1]["sport"] = "NBA"
        # Add enough rows to pass the len > 10 threshold
        for i in range(10):
            valid_nhl_rows.append({
                **valid_nhl_rows[0],
                "game_id": f"dup_{i}",
                "team": f"TM{i}",
                "opponent": f"OP{i}",
            })
        df = pd.DataFrame(valid_nhl_rows)
        result = validate_ingestion(df, sport="NHL", check_drift=True)
        assert result.passed is True
        assert any("drift" in w.lower() or "sport" in w.lower() for w in result.warnings)

    def test_no_drift_check_when_disabled(self, valid_nhl_rows):
        valid_nhl_rows[0]["sport"] = "NBA"
        valid_nhl_rows[1]["sport"] = "NBA"
        df = pd.DataFrame(valid_nhl_rows)
        result = validate_ingestion(df, sport="NHL", check_drift=False)
        # Should pass without drift warnings
        assert result.passed is True
        assert not any("drift" in w.lower() for w in result.warnings)

    def test_duplicate_detection_warning(self, valid_nhl_rows):
        """Same team appearing >4 times on same date triggers warning."""
        today = date.today() - timedelta(days=1)
        for i in range(5):
            valid_nhl_rows.append({
                "game_id": f"dup_{i}",
                "sport": "NHL",
                "team": "BOS",
                "opponent": f"OP{i}",
                "is_home": True,
                "game_date": today,
                "season": "2023",
                "points_for": 3,
                "points_against": 2,
                "won": True,
                "margin": 1,
                "off_rating": None,
                "def_rating": None,
                "pace": None,
            })
        df = pd.DataFrame(valid_nhl_rows)
        result = validate_ingestion(df, sport="NHL")
        assert result.passed is True
        assert any("duplicate" in w.lower() or "appear" in w.lower() for w in result.warnings)

    def test_empty_dataframe_passes(self):
        df = pd.DataFrame(columns=[
            "game_id", "sport", "team", "opponent", "is_home",
            "game_date", "season", "points_for", "points_against",
            "won", "margin", "off_rating", "def_rating", "pace",
        ])
        result = validate_ingestion(df, sport="NHL")
        assert result.passed is True
        assert result.row_count == 0

    def test_result_has_all_fields(self, valid_nhl_rows):
        df = pd.DataFrame(valid_nhl_rows)
        result = validate_ingestion(df, sport="NHL")
        assert isinstance(result, IngestionValidationResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "sport")
        assert hasattr(result, "row_count")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
        assert hasattr(result, "field_failures")
