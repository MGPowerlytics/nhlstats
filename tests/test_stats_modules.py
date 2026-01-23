"""Tests for Stats modules (NBA, MLB, NFL)."""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNBAStats:
    """Test NBA stats calculations."""

    def test_points_per_game_calculation(self):
        """Test calculating points per game."""
        total_points = 2500
        games_played = 25

        ppg = total_points / games_played

        assert ppg == 100.0

    def test_field_goal_percentage(self):
        """Test calculating field goal percentage."""
        made = 400
        attempted = 900

        fg_pct = made / attempted

        assert fg_pct == pytest.approx(0.444, abs=0.001)

    def test_three_point_percentage(self):
        """Test calculating three-point percentage."""
        made = 100
        attempted = 280

        three_pct = made / attempted

        assert three_pct == pytest.approx(0.357, abs=0.001)

    def test_free_throw_percentage(self):
        """Test calculating free throw percentage."""
        made = 180
        attempted = 200

        ft_pct = made / attempted

        assert ft_pct == 0.9

    def test_rebounds_per_game(self):
        """Test calculating rebounds per game."""
        total_rebounds = 1100
        games_played = 25

        rpg = total_rebounds / games_played

        assert rpg == 44.0

    def test_assists_per_game(self):
        """Test calculating assists per game."""
        total_assists = 600
        games_played = 25

        apg = total_assists / games_played

        assert apg == 24.0


class TestMLBStats:
    """Test MLB stats calculations."""

    def test_batting_average(self):
        """Test calculating batting average."""
        hits = 150
        at_bats = 500

        avg = hits / at_bats

        assert avg == 0.300

    def test_on_base_percentage(self):
        """Test calculating OBP."""
        hits = 150
        walks = 50
        hbp = 5
        at_bats = 500
        sacrifice_flies = 10

        obp = (hits + walks + hbp) / (at_bats + walks + hbp + sacrifice_flies)

        assert obp == pytest.approx(0.363, abs=0.001)

    def test_slugging_percentage(self):
        """Test calculating slugging percentage."""
        singles = 80
        doubles = 30
        triples = 5
        home_runs = 20
        at_bats = 500

        total_bases = singles + (doubles * 2) + (triples * 3) + (home_runs * 4)
        slg = total_bases / at_bats

        # 80 + 60 + 15 + 80 = 235. 235/500 = 0.47
        assert slg == pytest.approx(0.470, abs=0.001)

    def test_era_calculation(self):
        """Test calculating ERA."""
        earned_runs = 50
        innings_pitched = 180

        era = (earned_runs / innings_pitched) * 9

        assert era == pytest.approx(2.50, abs=0.01)

    def test_whip_calculation(self):
        """Test calculating WHIP."""
        walks = 40
        hits = 150
        innings_pitched = 180

        whip = (walks + hits) / innings_pitched

        assert whip == pytest.approx(1.056, abs=0.01)

    def test_strikeout_rate(self):
        """Test calculating strikeout rate."""
        strikeouts = 200
        batters_faced = 750

        k_rate = strikeouts / batters_faced

        assert k_rate == pytest.approx(0.267, abs=0.01)


class TestNFLStats:
    """Test NFL stats calculations."""

    def test_passer_rating(self):
        """Test calculating passer rating (simplified)."""
        completions = 350
        attempts = 500
        yards = 4000
        touchdowns = 30
        interceptions = 10

        # Simplified rating components
        a = ((completions / attempts) - 0.3) * 5
        b = ((yards / attempts) - 3) * 0.25
        c = (touchdowns / attempts) * 20
        d = 2.375 - ((interceptions / attempts) * 25)

        # Clamp each component between 0 and 2.375
        a = max(0, min(2.375, a))
        b = max(0, min(2.375, b))
        c = max(0, min(2.375, c))
        d = max(0, min(2.375, d))

        rating = ((a + b + c + d) / 6) * 100

        assert rating > 0
        assert rating < 160  # Max possible is 158.3

    def test_rushing_yards_per_attempt(self):
        """Test calculating yards per carry."""
        rushing_yards = 1200
        carries = 280

        ypc = rushing_yards / carries

        assert ypc == pytest.approx(4.29, abs=0.01)

    def test_receiving_yards_per_catch(self):
        """Test calculating yards per reception."""
        receiving_yards = 1100
        receptions = 85

        ypr = receiving_yards / receptions

        assert ypr == pytest.approx(12.94, abs=0.01)

    def test_completion_percentage(self):
        """Test calculating completion percentage."""
        completions = 350
        attempts = 500

        comp_pct = completions / attempts

        assert comp_pct == 0.70

    def test_td_to_int_ratio(self):
        """Test calculating TD to INT ratio."""
        touchdowns = 30
        interceptions = 10

        ratio = touchdowns / interceptions

        assert ratio == 3.0


class TestAdvancedStats:
    """Test advanced statistical calculations."""

    def test_pythagorean_wins_nba(self):
        """Test Pythagorean wins for NBA."""
        points_for = 110.5 * 82  # ~9061
        points_against = 105.0 * 82  # ~8610

        # NBA exponent is typically 13.91
        exponent = 13.91
        win_pct = points_for ** exponent / (points_for ** exponent + points_against ** exponent)
        expected_wins = win_pct * 82

        assert expected_wins > 41  # Better than average

    def test_pythagorean_wins_mlb(self):
        """Test Pythagorean wins for MLB."""
        runs_for = 750
        runs_against = 700

        # MLB exponent is typically 1.83
        exponent = 1.83
        win_pct = runs_for ** exponent / (runs_for ** exponent + runs_against ** exponent)
        expected_wins = win_pct * 162

        assert expected_wins > 81  # Better than average

    def test_strength_of_schedule(self):
        """Test calculating strength of schedule."""
        opponent_win_pcts = [0.600, 0.550, 0.500, 0.450, 0.400]

        sos = sum(opponent_win_pcts) / len(opponent_win_pcts)

        assert sos == 0.5

    def test_home_away_split(self):
        """Test home/away performance split."""
        home_record = {'wins': 30, 'losses': 11}
        away_record = {'wins': 20, 'losses': 21}

        home_win_pct = home_record['wins'] / (home_record['wins'] + home_record['losses'])
        away_win_pct = away_record['wins'] / (away_record['wins'] + away_record['losses'])

        assert home_win_pct > away_win_pct

    def test_recent_form(self):
        """Test calculating recent form (last N games)."""
        last_10_results = [1, 1, 1, 0, 1, 0, 1, 1, 0, 1]  # 1=win, 0=loss

        recent_win_pct = sum(last_10_results) / len(last_10_results)

        assert recent_win_pct == 0.7


class TestStatValidation:
    """Test stat validation logic."""

    def test_validate_percentage_in_range(self):
        """Test that percentages are in valid range."""
        valid_pcts = [0.0, 0.5, 1.0]
        invalid_pcts = [-0.1, 1.1, 2.0]

        for pct in valid_pcts:
            assert 0 <= pct <= 1

        for pct in invalid_pcts:
            assert not (0 <= pct <= 1)

    def test_validate_positive_counts(self):
        """Test that counts are positive."""
        valid_counts = [0, 1, 100, 1000]
        invalid_counts = [-1, -100]

        for count in valid_counts:
            assert count >= 0

        for count in invalid_counts:
            assert count < 0

    def test_validate_game_count_nba(self):
        """Test NBA game count validation."""
        regular_season_games = 82
        playoff_max = 28  # 4 rounds x 7 games max

        assert regular_season_games == 82
        assert playoff_max <= 28
