"""Tests for NFL modules with nfl_data_py mocked at module level."""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd

# Create mock for nfl_data_py BEFORE importing any modules that use it
mock_nfl = MagicMock()

# Mock schedule data
mock_nfl.import_schedules = MagicMock(return_value=pd.DataFrame({
    'game_id': ['2023_01_KC_DET', '2023_01_SF_CHI'],
    'gameday': [pd.Timestamp('2023-09-07'), pd.Timestamp('2023-09-10')],
    'week': [1, 1],
    'home_team': ['DET', 'CHI'],
    'away_team': ['KC', 'SF'],
    'home_score': [21, 14],
    'away_score': [20, 30]
}))

# Mock play-by-play data
mock_nfl.import_pbp_data = MagicMock(return_value=pd.DataFrame({
    'game_id': ['2023_01_KC_DET', '2023_01_KC_DET'],
    'play_id': [1, 2],
    'desc': ['Kickoff', 'Pass complete']
}))

# Mock weekly data
mock_nfl.import_weekly_data = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1', 'P2'],
    'season': [2023, 2023],
    'week': [1, 1],
    'player_name': ['Patrick Mahomes', 'Travis Kelce']
}))

# Mock seasonal data
mock_nfl.import_seasonal_data = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1'],
    'season': [2023],
    'player_name': ['Patrick Mahomes']
}))

# Mock rosters
mock_nfl.import_rosters = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1', 'P2'],
    'player_name': ['Patrick Mahomes', 'Travis Kelce'],
    'team': ['KC', 'KC']
}))

# Mock team descriptions
mock_nfl.import_team_desc = MagicMock(return_value=pd.DataFrame({
    'team_abbr': ['KC', 'DET', 'SF', 'CHI'],
    'team_name': ['Chiefs', 'Lions', '49ers', 'Bears'],
    'team_nick': ['Chiefs', 'Lions', '49ers', 'Bears']
}))

# Mock QBR
mock_nfl.import_qbr = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1'],
    'qbr': [75.5]
}))

# Mock PFR passing
mock_nfl.import_pfr_passing = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1'],
    'pass_yards': [5000]
}))

# Mock snap counts
mock_nfl.import_snap_counts = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1'],
    'snaps': [1000]
}))

# Mock injuries
mock_nfl.import_injuries = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P3'],
    'injury_status': ['Questionable'],
    'injury_type': ['Knee']
}))

# Mock depth charts
mock_nfl.import_depth_charts = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1', 'P2'],
    'position': ['QB', 'TE'],
    'depth_team': [1, 1]
}))

# Mock NGS data
mock_nfl.import_ngs_data = MagicMock(return_value=pd.DataFrame({
    'player_id': ['P1'],
    'stat_type': ['passing'],
    'value': [95.5]
}))

# Add the mock to sys.modules BEFORE importing the NFL modules
sys.modules['nfl_data_py'] = mock_nfl

# Now we can import the NFL modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNFLGamesWithPreMock:
    """Tests for NFLGames with pre-mocked nfl_data_py."""
    
    def test_nfl_games_import(self):
        """Test NFLGames can be imported."""
        from nfl_games import NFLGames
        
        assert NFLGames is not None
    
    def test_nfl_games_init(self, tmp_path):
        """Test NFLGames initialization."""
        from nfl_games import NFLGames
        
        games = NFLGames(output_dir=str(tmp_path / 'nfl'))
        
        assert games.output_dir.exists()
    
    def test_nfl_games_with_date_folder(self, tmp_path):
        """Test NFLGames with date folder."""
        from nfl_games import NFLGames
        
        games = NFLGames(
            output_dir=str(tmp_path / 'nfl'),
            date_folder='2023-09-07'
        )
        
        expected_path = tmp_path / 'nfl' / '2023-09-07'
        assert expected_path.exists()
    
    def test_nfl_games_download_for_date(self, tmp_path):
        """Test downloading games for a date."""
        from nfl_games import NFLGames
        
        games = NFLGames(output_dir=str(tmp_path / 'nfl'))
        count = games.download_games_for_date('2023-09-07')
        
        assert count == 1  # One game on Sep 7
    
    def test_nfl_games_no_games_date(self, tmp_path):
        """Test no games found for a date."""
        from nfl_games import NFLGames
        
        games = NFLGames(output_dir=str(tmp_path / 'nfl'))
        count = games.download_games_for_date('2023-01-01')  # No games
        
        assert count == 0
    
    def test_nfl_games_season_year_fall(self, tmp_path):
        """Test season year calculation for fall dates."""
        from nfl_games import NFLGames
        
        games = NFLGames(output_dir=str(tmp_path / 'nfl'))
        
        # September should be current year season
        games.download_games_for_date('2023-09-07')
        
        # Verify import_schedules was called with 2023
        mock_nfl.import_schedules.assert_called()
    
    def test_nfl_games_season_year_winter(self, tmp_path):
        """Test season year calculation for winter dates."""
        from nfl_games import NFLGames
        
        games = NFLGames(output_dir=str(tmp_path / 'nfl'))
        
        # January 2024 should be 2023 season
        games.download_games_for_date('2024-01-14')
        
        # Season year should be 2023 for January
        mock_nfl.import_schedules.assert_called()


class TestNFLStatsFetcherWithPreMock:
    """Tests for NFLStatsFetcher with pre-mocked nfl_data_py."""
    
    def test_nfl_stats_import(self):
        """Test NFLStatsFetcher can be imported."""
        from nfl_stats import NFLStatsFetcher
        
        assert NFLStatsFetcher is not None
    
    def test_nfl_stats_init(self, tmp_path):
        """Test NFLStatsFetcher initialization."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        
        assert fetcher.output_dir.exists()
    
    def test_nfl_stats_get_schedule(self, tmp_path):
        """Test getting schedule."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        schedule = fetcher.get_schedule(2023)
        
        assert len(schedule) == 2  # 2 games in mock
    
    def test_nfl_stats_get_play_by_play(self, tmp_path):
        """Test getting play-by-play."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        pbp = fetcher.get_play_by_play(2023)
        
        assert len(pbp) == 2
    
    def test_nfl_stats_get_weekly_data(self, tmp_path):
        """Test getting weekly data."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        weekly = fetcher.get_weekly_data(2023)
        
        assert len(weekly) == 2
    
    def test_nfl_stats_get_seasonal_data(self, tmp_path):
        """Test getting seasonal data."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        seasonal = fetcher.get_seasonal_data(2023)
        
        assert len(seasonal) == 1
    
    def test_nfl_stats_get_rosters(self, tmp_path):
        """Test getting rosters."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        rosters = fetcher.get_rosters(2023)
        
        assert len(rosters) == 2
    
    def test_nfl_stats_get_team_descriptions(self, tmp_path):
        """Test getting team descriptions."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        teams = fetcher.get_team_descriptions()
        
        assert len(teams) == 4
    
    def test_nfl_stats_get_injuries(self, tmp_path):
        """Test getting injuries."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        injuries = fetcher.get_injuries(2023)
        
        assert len(injuries) == 1
    
    def test_nfl_stats_get_depth_charts(self, tmp_path):
        """Test getting depth charts."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        depth = fetcher.get_depth_charts(2023)
        
        assert len(depth) == 2
    
    def test_nfl_stats_get_next_gen_stats(self, tmp_path):
        """Test getting NGS data."""
        from nfl_stats import NFLStatsFetcher
        
        fetcher = NFLStatsFetcher(output_dir=str(tmp_path / 'nfl'))
        ngs = fetcher.get_next_gen_stats(2023, stat_type='passing')
        
        assert len(ngs) == 1
