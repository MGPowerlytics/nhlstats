"""
Tests for the Elo argument parser.

The argument parser is critical for correctly parsing game results for Elo updates.
If it has bugs, Elo ratings become corrupted, predictions become wrong, and we lose money.
"""

import pytest
from plugins.elo.argument_parser import ArgumentParser


class TestArgumentParserExtractResultFromKwargs:
    """Tests for the _extract_result_from_kwargs method."""

    def test_extract_all_values_present(self):
        """Test extracting all result values when all are present in kwargs."""
        parser = ArgumentParser()
        kwargs = {
            "home_won": True,
            "home_score": 100,
            "away_score": 90,
            "home_win": True,  # alias for home_won
            "is_neutral": False,
        }

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert home_won is True
        assert home_score == 100
        assert away_score == 90
        assert home_win is True
        assert is_neutral is False

    def test_extract_missing_values(self):
        """Test extracting when some values are missing (should return None)."""
        parser = ArgumentParser()
        kwargs = {
            "home_won": False,
            # home_score missing
            # away_score missing
            "is_neutral": True,
        }

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert home_won is False
        assert home_score is None
        assert away_score is None
        assert home_win is None  # Not provided
        assert is_neutral is True

    def test_extract_empty_kwargs(self):
        """Test extracting from empty kwargs dictionary."""
        parser = ArgumentParser()
        kwargs = {}

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert home_won is None
        assert home_score is None
        assert away_score is None
        assert home_win is None
        assert is_neutral is False  # Default value

    def test_extract_with_default_is_neutral(self):
        """Test that is_neutral defaults to False when not provided."""
        parser = ArgumentParser()
        kwargs = {"home_won": True}

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert is_neutral is False

    def test_extract_with_explicit_is_neutral(self):
        """Test that is_neutral can be explicitly set to True."""
        parser = ArgumentParser()
        kwargs = {"home_won": True, "is_neutral": True}

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert is_neutral is True

    def test_extract_home_win_alias(self):
        """Test that home_win is extracted as an alias for home_won."""
        parser = ArgumentParser()
        kwargs = {"home_win": False, "home_score": 80, "away_score": 85}

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert home_won is None  # home_won not provided
        assert home_win is False  # home_win provided
        assert home_score == 80
        assert away_score == 85


class TestArgumentParserParseResult:
    """Tests for the parse_result method."""

    def test_parse_result_with_game_result_object(self):
        """Test parsing when input is already a GameResult object."""
        parser = ArgumentParser()
        from plugins.elo.elo_dataclasses import GameResult

        result_obj = GameResult(home_won=True, home_score=100, away_score=90)

        parsed = parser.parse_result(result_obj)
        assert parsed is result_obj  # Should return the same object

    def test_parse_result_with_kwargs(self):
        """Test parsing result from kwargs."""
        parser = ArgumentParser()

        parsed = parser.parse_result(None, home_won=True, home_score=100, away_score=90)

        assert parsed.home_won is True
        assert parsed.home_score == 100
        assert parsed.away_score == 90
        # Note: is_neutral is not part of GameResult

    def test_parse_result_with_home_win_alias(self):
        """Test parsing using home_win alias."""
        parser = ArgumentParser()

        parsed = parser.parse_result(
            None,
            home_win=False,  # alias for home_won
            home_score=80,
            away_score=85,
        )

        assert parsed.home_won is False
        assert parsed.home_score == 80
        assert parsed.away_score == 85
        # Note: is_neutral is not part of GameResult


class TestArgumentParserEdgeCases:
    """Tests for edge cases in argument parsing."""

    def test_extract_with_none_values(self):
        """Test extracting when values are explicitly None."""
        parser = ArgumentParser()
        kwargs = {
            "home_won": None,
            "home_score": None,
            "away_score": None,
            "home_win": None,
            "is_neutral": None,
        }

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert home_won is None
        assert home_score is None
        assert away_score is None
        assert home_win is None
        assert is_neutral is None  # Explicit None overrides default

    def test_extract_with_float_scores(self):
        """Test extracting float scores (should work)."""
        parser = ArgumentParser()
        kwargs = {
            "home_won": True,
            "home_score": 100.5,  # Float score
            "away_score": 90.0,  # Float score
        }

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert home_won is True
        assert home_score == 100.5
        assert away_score == 90.0

    def test_extract_with_zero_scores(self):
        """Test extracting zero scores (valid edge case)."""
        parser = ArgumentParser()
        kwargs = {
            "home_won": True,
            "home_score": 0,
            "away_score": 0,
            "is_neutral": True,
        }

        home_won, home_score, away_score, home_win, is_neutral = (
            parser._extract_result_from_kwargs(kwargs)
        )

        assert home_won is True
        assert home_score == 0
        assert away_score == 0
        assert is_neutral is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
