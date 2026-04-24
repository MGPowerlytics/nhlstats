import pytest
import sys
from pathlib import Path
from typing import Dict, Any

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from bet_loader import BetData, BetContext, BetRecommendation


def test_bet_data_from_dict_basic():
    """Test creating BetData from a basic dictionary."""
    data = {
        "home_team": "Lakers",
        "away_team": "Celtics",
        "side": "yes",
        "elo_prob": 0.65,
        "market_prob": 0.55,
        "edge": 0.10,
        "ticker": "NBA-123",
    }
    bet_data = BetData.from_dict(data)

    assert bet_data.home_team == "Lakers"
    assert bet_data.away_team == "Celtics"
    assert bet_data.side == "yes"
    assert bet_data.elo_prob == 0.65
    assert bet_data.market_prob == 0.55
    assert bet_data.edge == 0.10
    assert bet_data.ticker == "NBA-123"


def test_bet_data_from_dict_alternatives():
    """Test creating BetData with alternative key names."""
    data = {
        "player": "LeBron",
        "opponent": "KD",
        "bet_on": "no",
        "elo_prob": "0.7",
        "market_prob": 0.6,
    }
    bet_data = BetData.from_dict(data)

    assert bet_data.home_team == "LeBron"
    assert bet_data.away_team == "KD"
    assert bet_data.side == "no"
    assert bet_data.elo_prob == 0.7
    assert bet_data.market_prob == 0.6
    assert bet_data.edge == 0.0  # Default if missing


def test_bet_data_from_dict_preserves_optional_numeric_fields():
    """Test optional numeric fields round-trip through BetData.from_dict."""
    data = {
        "home_team": "Liverpool",
        "away_team": "Bournemouth",
        "side": "home",
        "elo_prob": 0.58,
        "market_prob": 0.47,
        "edge": 0.11,
        "expected_value": "0.234",
        "kelly_fraction": 0.056,
        "home_rating": "1612.4",
        "away_rating": 1498.2,
    }

    bet_data = BetData.from_dict(data)

    assert bet_data.expected_value == pytest.approx(0.234)
    assert bet_data.kelly_fraction == pytest.approx(0.056)
    assert bet_data.home_rating == pytest.approx(1612.4)
    assert bet_data.away_rating == pytest.approx(1498.2)


def test_bet_data_computed_values():
    """Test computed EV and Kelly."""
    bet_data = BetData(
        home_team="A", away_team="B", elo_prob=0.6, market_prob=0.5, edge=0.1
    )

    # EV = edge / market_prob = 0.1 / 0.5 = 0.2
    assert bet_data.computed_expected_value() == pytest.approx(0.2)

    # Kelly = (p*b - q) / b
    # p = 0.6, q = 0.4
    # b = (1/0.5) - 1 = 1
    # Kelly = (0.6*1 - 0.4) / 1 = 0.2
    assert bet_data.computed_kelly_fraction() == pytest.approx(0.2)


def test_bet_data_to_recommendation():
    """Test conversion to BetRecommendation."""
    bet_data = BetData(
        home_team="Lakers",
        away_team="Celtics",
        side="yes",
        elo_prob=0.6,
        market_prob=0.5,
        edge=0.1,
    )
    context = BetContext(sport="nba", date_str="2024-01-01", index=0)

    recommendation = bet_data.to_recommendation(context)

    assert recommendation.sport == "nba"
    assert recommendation.recommendation_date == "2024-01-01"
    assert recommendation.home_team == "Lakers"
    assert recommendation.bet_id == "nba_2024-01-01_Lakers_Celtics_yes_0"


def test_bet_recommendation_from_dict():
    """Test creating recommendation from dict."""
    data = {
        "home_team": "Lakers",
        "away_team": "Celtics",
        "side": "yes",
        "elo_prob": 0.6,
        "market_prob": 0.5,
        "edge": 0.1,
    }

    recommendation = BetRecommendation.from_dict(
        data, BetContext("nba", "2024-01-01", 5)
    )

    assert recommendation.sport == "nba"
    assert recommendation.recommendation_date == "2024-01-01"
    assert recommendation.bet_id == "nba_2024-01-01_Lakers_Celtics_yes_5"
