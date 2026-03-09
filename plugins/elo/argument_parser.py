"""
ArgumentParser - Handles parsing of various Elo update argument formats.

This class encapsulates all the complex logic for parsing different argument
formats (legacy, new, mixed) used in Elo update methods. It eliminates
feature envy by centralizing argument parsing logic.
"""

from typing import Optional, Union, Any, Tuple
from dataclasses import dataclass

from plugins.elo.elo_dataclasses import Matchup, GameResult, UpdateArgs


@dataclass
class ParsedUpdate:
    """Result of parsing update arguments."""

    matchup: Matchup
    result: GameResult


class ArgumentParser:
    """
    Parses various argument formats for Elo update methods.

    This class handles the complexity of supporting multiple argument formats
    (legacy positional, new dataclass, mixed) while providing a clean interface.
    """

    def parse_update_args(
        self,
        home_team: Optional[Union[Matchup, str]] = None,
        away_team: Optional[Union[GameResult, str, bool, float]] = None,
        home_won: Optional[Union[bool, float]] = None,
        is_neutral: bool = False,
        **kwargs,
    ) -> ParsedUpdate:
        """
        Consolidate argument parsing for update methods.
        Handles both primitive parameters and Matchup/GameResult objects.
        """
        # Create UpdateArgs object to encapsulate all arguments
        update_args = UpdateArgs(
            home_team=home_team,
            away_team=away_team,
            home_won=home_won,
            is_neutral=is_neutral,
            **kwargs,
        )

        return self._parse_update_args_from_object(update_args)

    def _parse_update_args_from_object(self, update_args: UpdateArgs) -> ParsedUpdate:
        """
        Parse update arguments from an UpdateArgs object.
        This eliminates feature envy by using a clean parameter object.
        """
        # 1. Extract raw inputs using helper methods
        raw_matchup = self._extract_raw_matchup(update_args)
        raw_result = self._extract_raw_result(update_args)
        h_won = self._extract_home_won_status(update_args)

        # 2. Extract Matchup and GameResult objects
        matchup = self._parse_matchup_from_args(raw_matchup, raw_result, update_args)
        result = self._parse_result_from_args(
            h_won if h_won is not None else raw_result, update_args
        )

        # 3. Handle legacy score-as-positional-args hack
        # This occurs when update(teamA, teamB, scoreA, scoreB) is called
        self._apply_legacy_score_hack(matchup, result, h_won, update_args.is_neutral)

        # 4. Final validations
        self._validate_parsed_args(matchup, result)

        return ParsedUpdate(matchup=matchup, result=result)

    def _extract_attribute(
        self, update_args: UpdateArgs, primary_attr: str, fallback_attr: str
    ) -> Any:
        """
        Extract an attribute from UpdateArgs with fallback.

        Args:
            update_args: The UpdateArgs instance to extract from
            primary_attr: Primary attribute name to check first
            fallback_attr: Fallback attribute name if primary is None

        Returns:
            The value of primary_attr if not None, otherwise fallback_attr
        """
        primary_value = getattr(update_args, primary_attr, None)
        if primary_value is not None:
            return primary_value
        return getattr(update_args, fallback_attr, None)

    def _extract_raw_matchup(
        self, update_args: UpdateArgs
    ) -> Optional[Union[Matchup, str]]:
        """
        Extract raw matchup input from UpdateArgs.

        Returns:
            Raw matchup input, preferring explicit matchup over home_team.
        """
        return self._extract_attribute(update_args, "matchup", "home_team")

    def _extract_raw_result(
        self, update_args: UpdateArgs
    ) -> Optional[Union[GameResult, str, bool, float]]:
        """
        Extract raw result input from UpdateArgs.

        Returns:
            Raw result input, preferring explicit result over away_team.
        """
        return self._extract_attribute(update_args, "result", "away_team")

    def _extract_home_won_status(
        self, update_args: UpdateArgs
    ) -> Optional[Union[bool, float]]:
        """
        Extract home won status from UpdateArgs, handling win/won aliases.

        Returns:
            Home won status, preferring home_won over home_win.
        """
        h_won = update_args.home_won
        if h_won is None:
            h_won = update_args.home_win
        return h_won

    def _apply_legacy_score_hack(
        self, matchup: Matchup, result: GameResult, h_won: Any, is_neutral: Any
    ) -> None:
        """Isolated legacy hack for score-as-positional-args."""
        if result.home_score is not None and result.away_score is not None:
            # If h_won and is_neutral were actually scores (> 1),
            # we need to ensure is_neutral isn't accidentally True
            if (
                isinstance(h_won, (int, float))
                and h_won > 1
                and isinstance(is_neutral, (int, float))
                and is_neutral > 1
            ):
                matchup.is_neutral = False

    def _validate_parsed_args(self, matchup: Matchup, result: GameResult) -> None:
        """Validate that we have the minimum required information."""
        if (
            not isinstance(matchup, Matchup)
            or not matchup.home_team
            or not matchup.away_team
        ):
            raise ValueError("Must provide home_team and away_team")

        if not isinstance(result, GameResult) or result.home_won is None:
            raise ValueError("Must provide home_won or scores")

    def _parse_matchup_from_args(
        self,
        matchup_input: Optional[Union[Matchup, str]],
        secondary_input: Optional[Any] = None,
        update_args: Optional[UpdateArgs] = None,
    ) -> Matchup:
        """Helper to parse Matchup object from various input styles using UpdateArgs."""
        if isinstance(matchup_input, Matchup):
            return matchup_input

        # Extract team names and neutral status from UpdateArgs or use defaults
        home_team, away_team, is_neutral = self._extract_matchup_components(update_args)

        # Override with positional inputs if they are strings (legacy support)
        if isinstance(matchup_input, str):
            home_team = matchup_input
        if isinstance(secondary_input, str):
            away_team = secondary_input

        return Matchup(
            home_team=home_team,
            away_team=away_team,
            is_neutral=is_neutral,
            game_date=None,  # game_date not currently in UpdateArgs
        )

    def _extract_matchup_components(
        self, update_args: Optional[UpdateArgs]
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Extract matchup components from UpdateArgs.

        Returns:
            Tuple of (home_team, away_team, is_neutral)
        """
        if update_args is not None:
            home_team = (
                update_args.home_team
                if isinstance(update_args.home_team, str)
                else None
            )
            away_team = (
                update_args.away_team
                if isinstance(update_args.away_team, str)
                else None
            )
            is_neutral = update_args.is_neutral
        else:
            # Fallback to defaults
            home_team = None
            away_team = None
            is_neutral = False

        return home_team, away_team, is_neutral

    def _parse_result_from_args(
        self,
        result_input: Optional[Union[GameResult, bool, float, int]],
        update_args: Optional[UpdateArgs] = None,
    ) -> GameResult:
        """Helper to parse GameResult object from various input styles using UpdateArgs."""
        if isinstance(result_input, GameResult):
            return result_input

        # Extract result components from UpdateArgs or use defaults
        home_won, home_score, away_score, home_win, is_neutral = (
            self._extract_result_components(update_args)
        )

        # Capture win status if it was passed in the result_input position
        if isinstance(result_input, (bool, float, int)) and home_won is None:
            home_won = result_input

        # Handle legacy positional score logic: home_won and is_neutral were used as scores
        if home_score is None and away_score is None:
            home_score, away_score, home_won = self._detect_scores_in_legacy_args(
                home_won, is_neutral
            )

        # Final outcome determination
        if home_won is None:
            home_won = self._determine_outcome(home_win, home_score, away_score)

        return GameResult(
            home_won=home_won, home_score=home_score, away_score=away_score
        )

    def _extract_result_components(self, update_args: Optional[UpdateArgs]) -> Tuple[
        Optional[Union[bool, float]],
        Optional[float],
        Optional[float],
        Optional[Union[bool, float]],
        bool,
    ]:
        """
        Extract result components from UpdateArgs.

        Returns:
            Tuple of (home_won, home_score, away_score, home_win, is_neutral)
        """
        if update_args is not None:
            home_won = update_args.home_won
            home_score = update_args.home_score
            away_score = update_args.away_score
            home_win = update_args.home_win
            is_neutral = update_args.is_neutral
        else:
            # Fallback to defaults
            home_won = None
            home_score = None
            away_score = None
            home_win = None
            is_neutral = False

        return home_won, home_score, away_score, home_win, is_neutral

    def _detect_scores_in_legacy_args(
        self, home_won: Any, is_neutral: Any
    ) -> tuple[Optional[float], Optional[float], Any]:
        """Detect if scores were passed in place of home_won/is_neutral."""
        home_score, away_score = None, None

        if isinstance(home_won, (int, float)) and isinstance(is_neutral, (int, float)):
            if home_won > 1 or is_neutral > 1:
                home_score = float(home_won)
                away_score = float(is_neutral)
                home_won = None

        return home_score, away_score, home_won

    def _determine_outcome(
        self,
        home_win: Optional[Any],
        home_score: Optional[float],
        away_score: Optional[float],
    ) -> Optional[Union[bool, float]]:
        """Determine home_won status from various inputs."""
        if home_win is not None:
            return home_win
        if home_score is not None and away_score is not None:
            return home_score > away_score
        return None

    def parse_matchup(
        self,
        matchup_input: Optional[Union[Matchup, str]],
        secondary_input: Optional[Any] = None,
        **kwargs,
    ) -> Matchup:
        """Helper to parse Matchup object from various input styles."""
        if isinstance(matchup_input, Matchup):
            return matchup_input

        # Default values from context
        home_team = kwargs.get("home_team")
        away_team = kwargs.get("away_team")
        is_neutral = kwargs.get("is_neutral", False)
        game_date = kwargs.get("game_date")

        # Override with positional inputs if they are strings (legacy support)
        if isinstance(matchup_input, str):
            home_team = matchup_input
        if isinstance(secondary_input, str):
            away_team = secondary_input

        return Matchup(
            home_team=home_team,
            away_team=away_team,
            is_neutral=is_neutral,
            game_date=game_date,
        )

    def parse_result(
        self, result_input: Optional[Union[GameResult, bool, float, int]], **kwargs
    ) -> GameResult:
        """Helper to parse GameResult object from various input styles."""
        if isinstance(result_input, GameResult):
            return result_input

        # Initial values from context
        home_won = kwargs.get("home_won")
        home_score = kwargs.get("home_score")
        away_score = kwargs.get("away_score")
        home_win = kwargs.get("home_win")
        is_neutral = kwargs.get("is_neutral")

        # Capture win status if it was passed in the result_input position
        if isinstance(result_input, (bool, float, int)) and home_won is None:
            home_won = result_input

        # Handle legacy positional score logic: home_won and is_neutral were used as scores
        if home_score is None and away_score is None:
            home_score, away_score, home_won = self._detect_scores_in_legacy_args(
                home_won, is_neutral
            )

        # Final outcome determination
        if home_won is None:
            home_won = self._determine_outcome(home_win, home_score, away_score)

        return GameResult(
            home_won=home_won, home_score=home_score, away_score=away_score
        )
