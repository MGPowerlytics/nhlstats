"""Adapter wrapping :class:`MLBEnsembleModel` behind the standard Elo interface.

The unified ``OddsComparator`` calls ``elo_system.predict(home, away)`` for
every matchup. The :class:`MLBEnsembleModel` instead expects an
:class:`MLBPredictionContext` carrying side information (rolling pythagorean
runs, rest days, venue, optional pitcher IDs).

This adapter:

* Exposes a ``.ratings`` dict that the DAG can populate from the DB.
* Pre-computes a per-team context cache (rolling runs scored/allowed, last
  game date) from ``mlb_games`` for the current season.
* Resolves a per-game venue lookup keyed by ``(home_team, away_team)`` from
  ``unified_games`` for the upcoming-games window.
* On ``predict(home, away)`` it builds an :class:`MLBPredictionContext` from
  the cached side information and delegates to the ensemble. When inputs
  are missing the underlying feature functions return 0, so the call
  degrades gracefully to plain team Elo + home-field advantage.

Pitcher Elo and bullpen ERA inputs are intentionally left at neutral
defaults until those feeds are ingested. The remaining signals
(pythagorean differential, rest, park factor) are computable from data
already in the warehouse and provide measurable lift on team-only Elo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple

from plugins.elo.mlb_elo_rating import MLBEloRating
from plugins.elo.mlb_ensemble import MLBEnsembleModel, MLBPredictionContext
from plugins.naming_resolver import NamingResolver, NamingContext


@dataclass
class _TeamSeasonStats:
    """Rolling per-team season aggregates used to build prediction contexts."""

    runs_scored: float = 0.0
    runs_allowed: float = 0.0
    last_game_date: Optional[date] = None
    bullpen_era: float = 4.0  # Default to league average ~4.00


@dataclass
class MLBEnsembleAdapter:
    """Drop-in replacement for :class:`MLBEloRating` that uses the ensemble.

    Attributes:
        ensemble: Underlying :class:`MLBEnsembleModel` whose ``team_elo``
            backs the public ``ratings`` view.
        venues: Map of ``(home_team, away_team)`` → venue name for upcoming
            matchups (populated from ``unified_games``).
        pitchers: Map of ``(home_team, away_team)`` → (home_pid, away_pid) for
            upcoming matchups (populated from ``unified_games``).
        team_stats: Map of canonical team name → :class:`_TeamSeasonStats`.
        reference_date: Reference "today" used to compute rest days. When
            ``None`` (default) the system clock is used.
    """

    ensemble: MLBEnsembleModel = field(default_factory=MLBEnsembleModel)
    venues: Dict[Tuple[str, str], str] = field(default_factory=dict)
    pitchers: Dict[Tuple[str, str], Tuple[Optional[str], Optional[str]]] = field(
        default_factory=dict
    )
    team_stats: Dict[str, _TeamSeasonStats] = field(default_factory=dict)
    reference_date: Optional[date] = None

    # Signal to OddsComparator that MLB uses governed (sabermetrics) predictions
    # instead of runtime Elo inference.  When True, calculate_probabilities()
    # calls _apply_governed_mlb_probabilities() → get_governed_probabilities().
    requires_governed_predictions: bool = True

    # ------------------------------------------------------------------
    # Drop-in Elo interface
    # ------------------------------------------------------------------
    @property
    def ratings(self) -> Dict[str, float]:
        """Return the underlying team-Elo ratings dict (read-write view)."""
        return self.ensemble.team_elo.ratings

    @ratings.setter
    def ratings(self, new_ratings: Dict[str, float]) -> None:
        """Replace the underlying team-Elo ratings (used by ``_load_elo_system``)."""
        self.ensemble.team_elo.ratings = dict(new_ratings or {})

    def get_rating(self, team: str) -> float:
        """Return the current team Elo rating.

        ``OddsComparator`` materializes recommendation metadata by calling
        ``elo_system.get_rating(team)`` after ``predict()`` succeeds. The
        adapter must expose the same surface as the plain team-Elo model so
        ensemble-backed MLB recommendations remain compatible with the shared
        betting pipeline.
        """
        return self.ensemble.team_elo.get_rating(team)

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Delegate expected-score calculation to the underlying team Elo."""
        return self.ensemble.team_elo.expected_score(rating_a, rating_b)

    def get_all_ratings(self) -> Dict[str, float]:
        """Return a copy of all current team ratings."""
        return dict(self.ensemble.team_elo.ratings)

    def has_real_rating(self, team: str) -> bool:
        """Check if team has a computed (non-default) Elo rating.

        Delegates to the underlying team Elo store so OddsComparator can
        safely guard against betting on teams with only the default 1500
        rating (i.e. teams the system has never processed a game for).

        Args:
            team: Canonical team name.

        Returns:
            True if the team's rating was computed from at least one game.
        """
        return self.ensemble.team_elo.has_real_rating(team)

    # ------------------------------------------------------------------
    # Governed probability bridge (reads sabermetrics model predictions)
    # ------------------------------------------------------------------

    def get_governed_probabilities(self, game_id: str) -> dict[str, float] | None:
        """Return ``{home: prob, away: prob}`` from the calibrated moneyline model.

        Queries ``mlb_model_predictions`` for the most recent non-abstaining
        home/away predictions for *game_id*.  Returns ``None`` when no enabled
        predictions are available (the caller falls back to abstentions).
        """
        from plugins.db_manager import default_db

        db = getattr(self, "_db", None) or default_db

        rows = db.fetch_df(
            """
            SELECT outcome_name, model_prob
            FROM mlb_model_predictions
            WHERE game_id = :game_id
              AND abstain = FALSE
              AND model_prob IS NOT NULL
            ORDER BY created_at DESC
            """,
            {"game_id": str(game_id)},
        )
        if rows is None or rows.empty:
            return None

        probs: dict[str, float] = {}
        for _, row in rows.iterrows():
            name = str(row["outcome_name"]).lower()
            if name not in probs:  # first (most recent) wins
                probs[name] = float(row["model_prob"])

        if "home" not in probs or "away" not in probs:
            return None
        return probs

    @property
    def governed_prediction_metadata(self) -> dict[str, str]:
        """Metadata stamped into governed bet recommendations."""
        from plugins.db_manager import default_db

        db = getattr(self, "_db", None) or default_db
        row = db.fetch_df(
            """
            SELECT model_version, run_date::TEXT AS run_date
            FROM mlb_model_predictions
            WHERE abstain = FALSE
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if row is not None and not row.empty:
            return {
                "model_version": str(row["model_version"].iloc[0]),
                "run_date": str(row["run_date"].iloc[0]),
            }
        return {"model_version": "unknown", "run_date": "unknown"}

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, home_team: str, away_team: str) -> float:
        """Return ensemble P(home wins).

        Builds an :class:`MLBPredictionContext` from cached side data, then
        delegates to :meth:`MLBEnsembleModel.predict`. Missing context
        degrades to neutral defaults that contribute zero adjustment.
        """
        ctx = self._build_context(home_team, away_team)
        return self.ensemble.predict(ctx)

    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: bool,
        home_pitcher_id: Optional[str] = None,
        away_pitcher_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Update team and pitcher Elo ratings based on game outcome.

        Delegates to the underlying ensemble model which updates both
        the team Elo system and the pitcher Elo ladder.
        """
        # First update team Elo (standard interface)
        self.ensemble.team_elo.update(home_team, away_team, home_won, **kwargs)

        # Then update pitcher Elo if IDs are provided
        if home_pitcher_id and away_pitcher_id:
            ctx = self._build_context(home_team, away_team)
            # Override with actual pitchers from the result
            ctx.home_pitcher_id = str(home_pitcher_id)
            ctx.away_pitcher_id = str(away_pitcher_id)
            self.ensemble.observe(
                ctx, home_won, kwargs.get("game_date") or date.today()
            )

    # ------------------------------------------------------------------
    # Context construction
    # ------------------------------------------------------------------
    def _build_context(self, home_team: str, away_team: str) -> MLBPredictionContext:
        """Assemble an :class:`MLBPredictionContext` for a matchup."""
        h_stats = self.team_stats.get(home_team) or _TeamSeasonStats()
        a_stats = self.team_stats.get(away_team) or _TeamSeasonStats()
        venue = self.venues.get((home_team, away_team))
        p_ids = self.pitchers.get((home_team, away_team), (None, None))
        ref = self.reference_date or date.today()

        return MLBPredictionContext(
            home_team=home_team,
            away_team=away_team,
            venue=venue,
            home_runs_scored_ytd=h_stats.runs_scored,
            home_runs_allowed_ytd=h_stats.runs_allowed,
            away_runs_scored_ytd=a_stats.runs_scored,
            away_runs_allowed_ytd=a_stats.runs_allowed,
            home_rest_days=_rest_days(h_stats.last_game_date, ref),
            away_rest_days=_rest_days(a_stats.last_game_date, ref),
            home_pitcher_id=p_ids[0],
            away_pitcher_id=p_ids[1],
            home_bullpen_era=h_stats.bullpen_era,
            away_bullpen_era=a_stats.bullpen_era,
        )

    # ------------------------------------------------------------------
    # Population helpers (called by the DAG)
    # ------------------------------------------------------------------
    def populate_from_db(
        self,
        db,
        season_year: Optional[int] = None,
        reference_date: Optional[date] = None,
    ) -> None:
        """Populate ``team_stats``, ``form``, and ``venues`` from the warehouse.

        Streams completed season games in chronological order so the
        ensemble's :class:`RecentFormTracker` reflects each team's most
        recent results — without this, ``ensemble.form`` stays empty after
        ``populate_from_db`` and the form feature contributes 0 to every
        prediction.

        Args:
            db: A :class:`plugins.db_manager.DBManager`-compatible object
                exposing ``fetch_df(query, params)``.
            season_year: Season to aggregate (defaults to the year of
                ``reference_date`` or today).
            reference_date: "Today" used for rest-day calculations and to
                bound the season aggregates (only games before this date
                contribute). Defaults to today.
        """
        ref = reference_date or date.today()
        self.reference_date = ref
        self._db = db  # cache for governed-probability queries
        year = season_year or ref.year
        self._load_team_stats_and_form(db, year, ref)
        self._load_bullpen_era(db, ref)
        self._load_venues_and_pitchers(db, ref)

    def _load_team_stats_and_form(self, db, year: int, ref: date) -> None:
        """Aggregate season runs/last-game-date and replay form per team.

        A single chronological scan of completed games feeds two trackers:

        * ``self.team_stats`` — cumulative runs scored/allowed and most
          recent game date (used to derive Pythagorean expectation and
          rest days).
        * ``self.ensemble.form`` — :class:`RecentFormTracker` rolling
          window of recent W/L outcomes per team.
        """
        query = """
            SELECT game_date, home_team, away_team, home_score, away_score
            FROM mlb_games
            WHERE EXTRACT(YEAR FROM game_date) = :year
              AND game_date < :ref
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND game_type IN ('R', 'D', 'L', 'W', 'F')
              AND status IN ('Final', 'Game Over', 'Completed Early')
            ORDER BY game_date
        """
        df = db.fetch_df(query, {"year": int(year), "ref": ref})
        if df is None or df.empty:
            return

        stats: Dict[str, _TeamSeasonStats] = {}
        # Reset form so re-population is idempotent.
        self.ensemble.form._records.clear()

        for row in df.itertuples(index=False):
            gd = _coerce_date(row.game_date)
            home, away = row.home_team, row.away_team
            hs, as_ = float(row.home_score), float(row.away_score)

            # Cumulative season stats
            h = stats.setdefault(home, _TeamSeasonStats())
            a = stats.setdefault(away, _TeamSeasonStats())
            h.runs_scored += hs
            h.runs_allowed += as_
            a.runs_scored += as_
            a.runs_allowed += hs
            if h.last_game_date is None or gd > h.last_game_date:
                h.last_game_date = gd
            if a.last_game_date is None or gd > a.last_game_date:
                a.last_game_date = gd

            # Recent-form tracker (chronological order matters)
            home_won = hs > as_
            self.ensemble.form.update(home, home_won)
            self.ensemble.form.update(away, not home_won)

        self.team_stats = stats

    def _load_bullpen_era(self, db, ref: date) -> None:
        """Compute rolling bullpen strength proxy (14-day team ERA)."""
        query = """
            SELECT mlb_team_game_stats_ext.team, AVG(era) as avg_era
            FROM mlb_team_game_stats_ext
            JOIN team_game_stats ON mlb_team_game_stats_ext.game_id = team_game_stats.game_id
                                AND mlb_team_game_stats_ext.team = team_game_stats.team
            WHERE team_game_stats.game_date < :ref
              AND team_game_stats.game_date >= :ref - INTERVAL '14 days'
            GROUP BY mlb_team_game_stats_ext.team
        """
        df = db.fetch_df(query, {"ref": ref})
        if df is None or df.empty:
            return

        resolver = NamingResolver()
        for row in df.itertuples(index=False):
            # Resolve abbreviation (e.g. 'HOU') to canonical name (e.g. 'Houston Astros')
            canon_name = resolver.resolve(
                NamingContext(sport="mlb", source="statsapi", name=row.team)
            )
            if canon_name in self.team_stats:
                self.team_stats[canon_name].bullpen_era = float(row.avg_era)

    def _load_venues_and_pitchers(self, db, ref: date) -> None:
        """Resolve venues and starting pitchers for upcoming MLB games."""
        end = ref + timedelta(days=4)
        query = """
            SELECT home_team_name AS home_team,
                   away_team_name AS away_team,
                   venue,
                   home_pitcher_id,
                   away_pitcher_id
            FROM unified_games
            WHERE LOWER(sport) = 'mlb'
              AND game_date >= :ref
              AND game_date < :end
              AND (venue IS NOT NULL OR home_pitcher_id IS NOT NULL)
        """
        df = db.fetch_df(query, {"ref": ref, "end": end})
        if df is None or df.empty:
            return
        for row in df.itertuples(index=False):
            # Convert row to dict for safer access if needed, or use getattr
            row_dict = row._asdict()
            h_team = row_dict.get("home_team")
            a_team = row_dict.get("away_team")
            venue = row_dict.get("venue")
            h_pid = row_dict.get("home_pitcher_id")
            a_pid = row_dict.get("away_pitcher_id")

            if venue:
                self.venues[(h_team, a_team)] = venue
            if h_pid or a_pid:
                self.pitchers[(h_team, a_team)] = (h_pid, a_pid)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_ratings(self, data_dir: str = "data") -> None:
        """Save both team and pitcher Elo ratings."""
        # Standard team Elo helper already handled by the DAG,
        # but we need to save the pitcher ladder.
        p_path = f"{data_dir}/mlb_pitcher_elo_ratings.csv"
        self.ensemble.pitcher_elo.save_ratings(p_path)
        print(
            f"✓ Saved {len(self.ensemble.pitcher_elo.all_ratings())} pitcher ratings to {p_path}"
        )

    def load_ratings(self, data_dir: str = "data") -> None:
        """Load pitcher Elo ratings from CSV."""
        p_path = f"{data_dir}/mlb_pitcher_elo_ratings.csv"
        self.ensemble.pitcher_elo.load_ratings(p_path)
        print(
            f"✓ Loaded {len(self.ensemble.pitcher_elo.all_ratings())} pitcher ratings from {p_path}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rest_days(last: Optional[date], ref: date) -> int:
    """Return rest days between ``last`` and ``ref``, capped to ``[0, 7]``.

    Returns 2 (neutral) when ``last`` is unknown.
    """
    if last is None:
        return 2
    delta = (ref - last).days - 1
    return max(0, min(7, delta))


def _coerce_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
