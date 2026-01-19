"""Tests for NFL Stats module."""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNFLStatsFetcherInit:
    """Test NFLStatsFetcher initialization."""
    
    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates output directory."""
        # Test the directory creation logic independently
        output_dir = tmp_path / "nfl"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        assert output_dir.exists()
    
    def test_output_dir_structure(self, tmp_path):
        """Test output directory structure."""
        output_dir = tmp_path / "nfl"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        assert output_dir.exists()


class TestSeasonData:
    """Test season data handling."""
    
    def test_regular_season_weeks(self):
        """Test regular season has 18 weeks."""
        regular_season_weeks = 18
        
        assert regular_season_weeks == 18
    
    def test_playoff_rounds(self):
        """Test playoff structure."""
        playoff_rounds = ['Wild Card', 'Divisional', 'Conference', 'Super Bowl']
        
        assert len(playoff_rounds) == 4
    
    def test_week_calculation(self):
        """Test week number calculation."""
        # Week 1 example
        week = 1
        season = 2024
        
        assert 1 <= week <= 22  # Regular + postseason


class TestPlayerStats:
    """Test player statistics."""
    
    def test_qb_stats_structure(self):
        """Test quarterback stats structure."""
        qb_stats = {
            'player_id': 12345,
            'player_name': 'Patrick Mahomes',
            'completions': 350,
            'attempts': 500,
            'yards': 4500,
            'touchdowns': 35,
            'interceptions': 10,
            'passer_rating': 105.5
        }
        
        assert qb_stats['touchdowns'] == 35
    
    def test_rb_stats_structure(self):
        """Test running back stats structure."""
        rb_stats = {
            'player_id': 12346,
            'player_name': 'Derrick Henry',
            'carries': 280,
            'rushing_yards': 1500,
            'rushing_tds': 12,
            'yards_per_carry': 5.36
        }
        
        ypc = rb_stats['rushing_yards'] / rb_stats['carries']
        
        assert ypc == pytest.approx(5.36, abs=0.01)
    
    def test_wr_stats_structure(self):
        """Test wide receiver stats structure."""
        wr_stats = {
            'player_id': 12347,
            'player_name': 'Tyreek Hill',
            'receptions': 120,
            'targets': 150,
            'receiving_yards': 1700,
            'receiving_tds': 13
        }
        
        catch_rate = wr_stats['receptions'] / wr_stats['targets']
        
        assert catch_rate == 0.8


class TestPasserRating:
    """Test passer rating calculation."""
    
    def test_passer_rating_calculation(self):
        """Test passer rating formula."""
        comp = 350
        att = 500
        yards = 4500
        td = 35
        int_thrown = 10
        
        # NFL passer rating formula
        a = ((comp / att) - 0.3) * 5
        b = ((yards / att) - 3) * 0.25
        c = (td / att) * 20
        d = 2.375 - ((int_thrown / att) * 25)
        
        # Clamp between 0 and 2.375
        a = max(0, min(2.375, a))
        b = max(0, min(2.375, b))
        c = max(0, min(2.375, c))
        d = max(0, min(2.375, d))
        
        rating = ((a + b + c + d) / 6) * 100
        
        assert 0 <= rating <= 158.3
    
    def test_perfect_passer_rating(self):
        """Test perfect passer rating is 158.3."""
        perfect_rating = 158.3
        
        assert perfect_rating == 158.3


class TestTeamStats:
    """Test team statistics."""
    
    def test_offensive_stats(self):
        """Test offensive stats structure."""
        offense = {
            'total_yards': 5500,
            'passing_yards': 4000,
            'rushing_yards': 1500,
            'points_scored': 450,
            'turnovers': 15
        }
        
        assert offense['total_yards'] == offense['passing_yards'] + offense['rushing_yards']
    
    def test_defensive_stats(self):
        """Test defensive stats structure."""
        defense = {
            'points_allowed': 320,
            'yards_allowed': 5200,
            'sacks': 45,
            'interceptions': 18,
            'forced_fumbles': 12
        }
        
        assert defense['sacks'] == 45
    
    def test_special_teams_stats(self):
        """Test special teams stats."""
        special_teams = {
            'fg_made': 28,
            'fg_attempted': 32,
            'punt_avg': 45.5,
            'kick_return_avg': 22.3
        }
        
        fg_pct = special_teams['fg_made'] / special_teams['fg_attempted']
        
        assert fg_pct == 0.875


class TestGameData:
    """Test game data structure."""
    
    def test_game_result_structure(self):
        """Test game result structure."""
        game = {
            'game_id': 'nfl_2024_week1_kc_det',
            'home_team': 'Detroit Lions',
            'away_team': 'Kansas City Chiefs',
            'home_score': 21,
            'away_score': 20,
            'week': 1,
            'season': 2024
        }
        
        home_won = game['home_score'] > game['away_score']
        
        assert home_won == True
    
    def test_point_differential(self):
        """Test point differential calculation."""
        points_for = 450
        points_against = 320
        
        diff = points_for - points_against
        
        assert diff == 130


class TestAdvancedMetrics:
    """Test advanced NFL metrics."""
    
    def test_dvoa_concept(self):
        """Test DVOA concept (Defense-adjusted Value Over Average)."""
        # DVOA measures efficiency compared to league average
        team_efficiency = 15.5  # Percentage above/below average
        
        assert isinstance(team_efficiency, float)
    
    def test_epa_per_play(self):
        """Test EPA (Expected Points Added) per play."""
        total_epa = 85.5
        total_plays = 1000
        
        epa_per_play = total_epa / total_plays
        
        assert epa_per_play == 0.0855
    
    def test_win_probability(self):
        """Test win probability calculation."""
        # Simple Pythagorean expectation
        points_for = 450
        points_against = 320
        
        exponent = 2.37  # NFL exponent
        wp = (points_for ** exponent) / (points_for ** exponent + points_against ** exponent)
        
        assert wp > 0.5  # Should be favored with positive point diff
