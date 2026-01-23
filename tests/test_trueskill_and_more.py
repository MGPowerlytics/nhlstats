"""
Tests for compare_elo_trueskill_nhl.py and other remaining 0% modules.
"""
import pytest
import numpy as np
import pandas as pd


class TestCompareEloTrueskillNHL:
    """Tests for compare_elo_trueskill_nhl.py."""

    def test_import(self):
        """Test module import."""
        from compare_elo_trueskill_nhl import _clamp_probs, Metrics
        assert _clamp_probs is not None
        assert Metrics is not None

    def test_clamp_probs(self):
        """Test _clamp_probs function."""
        from compare_elo_trueskill_nhl import _clamp_probs

        probs = np.array([0.0, 0.5, 1.0])
        result = _clamp_probs(probs)
        assert all(result > 0)
        assert all(result < 1)
        assert result[1] == pytest.approx(0.5)

    def test_clamp_probs_with_eps(self):
        """Test _clamp_probs with custom eps."""
        from compare_elo_trueskill_nhl import _clamp_probs

        probs = np.array([0.0, 1.0])
        result = _clamp_probs(probs, eps=0.01)
        assert result[0] == 0.01
        assert result[1] == 0.99

    def test_metrics_dataclass(self):
        """Test Metrics dataclass."""
        from compare_elo_trueskill_nhl import Metrics

        m = Metrics(
            n_games=100,
            baseline_home_win_rate=0.55,
            accuracy=0.60,
            brier=0.22,
            log_loss=0.65
        )
        assert m.n_games == 100
        assert m.accuracy == 0.60

    def test_team_trueskill_class(self):
        """Test TeamTrueSkill class if available."""
        try:
            from compare_elo_trueskill_nhl import TeamTrueSkill
            ts = TeamTrueSkill()
            assert ts is not None
        except ImportError:
            pass

    def test_trueskill_rating_class(self):
        """Test TrueSkillRating class if available."""
        try:
            from compare_elo_trueskill_nhl import TrueSkillRating
            rating = TrueSkillRating()
            assert rating is not None
        except ImportError:
            pass


class TestCompareModulesHelper:
    """Tests for helper functions in compare modules."""

    def test_calibrated_clamp_probs(self):
        """Test _clamp_probs from calibrated module."""
        from compare_elo_calibrated_current_season import _clamp_probs

        probs = np.array([0.0, 0.5, 1.0])
        result = _clamp_probs(probs)
        assert all(result > 0)
        assert all(result < 1)

    def test_calibrated_logit(self):
        """Test _logit from calibrated module."""
        from compare_elo_calibrated_current_season import _logit

        probs = np.array([0.25, 0.5, 0.75])
        result = _logit(probs)
        assert result[1] == pytest.approx(0.0, abs=0.01)

    def test_markov_clamp_probs(self):
        """Test _clamp_probs from markov module."""
        from compare_elo_markov_current_season import _clamp_probs

        probs = np.array([0.0, 0.5, 1.0])
        result = _clamp_probs(probs)
        assert all(result > 0)
        assert all(result < 1)


class TestMoreCoverage:
    """Additional tests for more coverage."""

    def test_nba_elo_expected_score(self):
        """Test NBA Elo expected_score method."""
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()
        result = elo.expected_score(1600, 1400)
        assert 0.7 < result < 0.8  # Higher rated should be ~75%

    def test_nhl_elo_expected_score(self):
        """Test NHL Elo expected_score method."""
        from plugins.elo import NHLEloRating

        elo = NHLEloRating()
        result = elo.expected_score(1600, 1400)
        assert 0.7 < result < 0.8

    def test_mlb_elo_expected_score(self):
        """Test MLB Elo expected_score method."""
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        result = elo.expected_score(1600, 1400)
        assert 0.7 < result < 0.8

    def test_nfl_elo_expected_score(self):
        """Test NFL Elo expected_score method."""
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        result = elo.expected_score(1600, 1400)
        assert 0.7 < result < 0.8

    def test_epl_elo_predict(self):
        """Test EPL Elo predict method."""
        from plugins.elo import EPLEloRating

        elo = EPLEloRating()
        result = elo.predict('Arsenal', 'Chelsea')
        assert 0 < result < 1

    def test_ncaab_elo_predict(self):
        """Test NCAAB Elo predict method."""
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        result = elo.predict('Duke', 'UNC')
        assert 0 < result < 1


class TestGamesModulesHelpers:
    """Tests for game module helper functions."""

    def test_nba_games_output_dir(self):
        """Test NBAGames output directory setting."""
        from nba_games import NBAGames
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            games = NBAGames(output_dir=tmpdir)
            assert tmpdir in str(games.output_dir)

    def test_mlb_games_output_dir(self):
        """Test MLBGames output directory setting."""
        from mlb_games import MLBGames
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            games = MLBGames(output_dir=tmpdir)
            assert tmpdir in str(games.output_dir)

    def test_tennis_games_data_dir(self):
        """Test TennisGames data directory setting."""
        from tennis_games import TennisGames
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            games = TennisGames(data_dir=tmpdir)
            assert tmpdir in str(games.data_dir)

    def test_epl_games_data_dir(self):
        """Test EPLGames data directory setting."""
        from epl_games import EPLGames
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            games = EPLGames(data_dir=tmpdir)
            assert tmpdir in str(games.data_dir)

    def test_ligue1_games_data_dir(self):
        """Test Ligue1Games data directory setting."""
        from ligue1_games import Ligue1Games
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            games = Ligue1Games(data_dir=tmpdir)
            assert tmpdir in str(games.data_dir)

    def test_ncaab_games_data_dir(self):
        """Test NCAABGames data directory setting."""
        from ncaab_games import NCAABGames
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            games = NCAABGames(data_dir=tmpdir)
            assert tmpdir in str(games.data_dir)
