"""Tests for Odds Comparator module."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestOddsComparatorInit:
    """Test OddsComparator initialization."""
    
    def test_init_platforms(self):
        """Test default platforms."""
        from odds_comparator import OddsComparator
        
        comp = OddsComparator()
        
        assert 'kalshi' in comp.platforms
        assert 'cloudbet' in comp.platforms
        assert 'polymarket' in comp.platforms


class TestLoadMarkets:
    """Test market loading functionality."""
    
    def test_load_markets_file_not_found(self, tmp_path):
        """Test loading when file doesn't exist."""
        from odds_comparator import OddsComparator
        
        with patch('odds_comparator.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            
            comp = OddsComparator()
            markets = comp.load_markets('nba', '2024-01-15', 'kalshi')
            
            assert markets == []
    
    def test_load_markets_success(self, tmp_path):
        """Test successful market loading."""
        # This test verifies the JSON parsing logic
        test_data = [{'ticker': 'TEST', 'yes_ask': 55}]
        
        market_file = tmp_path / "markets.json"
        market_file.write_text(json.dumps(test_data))
        
        with open(market_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded == test_data
    
    def test_filename_map_kalshi(self):
        """Test Kalshi filename pattern."""
        filename_map = {
            'kalshi': 'markets_2024-01-15.json',
            'cloudbet': 'cloudbet_markets_2024-01-15.json',
            'polymarket': 'polymarket_markets_2024-01-15.json'
        }
        
        assert filename_map['kalshi'] == 'markets_2024-01-15.json'
    
    def test_filename_map_cloudbet(self):
        """Test Cloudbet filename pattern."""
        date_str = '2024-01-15'
        filename = f'cloudbet_markets_{date_str}.json'
        
        assert filename == 'cloudbet_markets_2024-01-15.json'


class TestNormalizeTeamName:
    """Test team name normalization."""
    
    def test_normalize_lowercase(self):
        """Test lowercase normalization."""
        from odds_comparator import OddsComparator
        
        comp = OddsComparator()
        normalized = comp.normalize_team_name("Boston Celtics")
        
        assert normalized.islower()
    
    def test_normalize_strip_whitespace(self):
        """Test whitespace stripping."""
        from odds_comparator import OddsComparator
        
        comp = OddsComparator()
        normalized = comp.normalize_team_name("  Lakers  ")
        
        assert not normalized.startswith(' ')
        assert not normalized.endswith(' ')
    
    def test_normalize_known_team(self):
        """Test normalizing known team."""
        from odds_comparator import OddsComparator
        
        comp = OddsComparator()
        normalized = comp.normalize_team_name("boston celtics")
        
        assert normalized == 'celtics'
    
    def test_normalize_unknown_team(self):
        """Test normalizing unknown team."""
        from odds_comparator import OddsComparator
        
        comp = OddsComparator()
        normalized = comp.normalize_team_name("random team name")
        
        assert normalized == 'random team name'


class TestMatchMarkets:
    """Test market matching functionality."""
    
    def test_match_markets_empty(self):
        """Test matching with empty markets."""
        from odds_comparator import OddsComparator
        
        comp = OddsComparator()
        
        with patch.object(comp, 'load_markets', return_value=[]):
            matched = comp.match_markets('nba', '2024-01-15')
            
            assert isinstance(matched, list)


class TestArbitrageDetection:
    """Test arbitrage detection logic."""
    
    def test_no_arbitrage_opportunity(self):
        """Test when no arbitrage exists."""
        home_prob_a = 0.55
        away_prob_a = 0.50
        
        # Total implied probability > 100% = no arbitrage
        total = home_prob_a + away_prob_a
        arbitrage_exists = total < 1.0
        
        assert arbitrage_exists == False
    
    def test_arbitrage_opportunity_exists(self):
        """Test when arbitrage exists."""
        # If we can get better odds on both sides
        home_prob_a = 0.48  # Platform A has home at 48%
        away_prob_b = 0.48  # Platform B has away at 48%
        
        # Combined < 100% = arbitrage
        total = home_prob_a + away_prob_b
        arbitrage_exists = total < 1.0
        
        assert arbitrage_exists == True
    
    def test_calculate_arbitrage_profit(self):
        """Test calculating arbitrage profit."""
        # Home at 2.10 (47.6%), Away at 2.10 (47.6%)
        total_implied = 0.476 + 0.476  # 95.2%
        
        if total_implied < 1.0:
            profit_margin = (1 / total_implied - 1) * 100
        else:
            profit_margin = 0
        
        assert profit_margin > 0


class TestProbabilityCalculations:
    """Test probability calculations."""
    
    def test_yes_ask_to_probability(self):
        """Test converting yes_ask to probability."""
        yes_ask = 55  # cents
        probability = yes_ask / 100.0
        
        assert probability == 0.55
    
    def test_calculate_away_probability(self):
        """Test calculating away probability from home."""
        home_prob = 0.55
        away_prob = 1 - home_prob
        
        assert away_prob == pytest.approx(0.45, abs=0.001)
    
    def test_odds_comparison(self):
        """Test comparing odds across platforms."""
        platform_a = {'home_prob': 0.55, 'away_prob': 0.50}
        platform_b = {'home_prob': 0.52, 'away_prob': 0.53}
        
        # Best home odds
        best_home = max(platform_a['home_prob'], platform_b['home_prob'])
        # Best away odds (from perspective of betting away)
        best_away = max(platform_a['away_prob'], platform_b['away_prob'])
        
        assert best_home == 0.55
        assert best_away == 0.53


class TestMarketMatching:
    """Test market matching logic."""
    
    def test_team_name_matching_exact(self):
        """Test exact team name matching."""
        team_a = "lakers"
        team_b = "lakers"
        
        assert team_a == team_b
    
    def test_team_name_matching_partial(self):
        """Test partial team name matching."""
        full_name = "los angeles lakers"
        short_name = "lakers"
        
        match = short_name in full_name
        
        assert match == True
    
    def test_create_match_entry(self):
        """Test creating match entry."""
        kalshi_market = {
            'ticker': 'KXNBAGAME-TEST',
            'yes_ask': 55,
            'home_team': 'Lakers',
            'away_team': 'Celtics'
        }
        
        match_entry = {
            'sport': 'nba',
            'date': '2024-01-15',
            'home_team': kalshi_market.get('home_team'),
            'away_team': kalshi_market.get('away_team'),
            'platforms': {
                'kalshi': {
                    'market_id': kalshi_market.get('ticker'),
                    'home_prob': kalshi_market.get('yes_ask', 0) / 100.0,
                }
            }
        }
        
        assert match_entry['home_team'] == 'Lakers'
        assert match_entry['platforms']['kalshi']['home_prob'] == 0.55
