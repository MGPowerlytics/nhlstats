"""Platt scaling calibration for Elo win probabilities.

Fits a per-sport logistic regression (Platt scaling) on historical
(elo_prob, actual_outcome) pairs from settled bets and recommendations,
correcting Elo's systematic over/under-estimation of win probabilities.
"""

from __future__ import annotations

import math
import os
import json
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression

from plugins.db_manager import DBManager, default_db


class CalibratorNotFittedError(RuntimeError):
    """Raised when ``calibrate`` is called for a sport without a fitted model."""

    def __init__(self, sport: str) -> None:
        super().__init__(f"No calibration model fitted for '{sport}'")
        self.sport = sport


# Minimum number of settled samples (bets or recommendations) required before fitting.
MIN_BETS_FOR_FIT = 30


@dataclass(frozen=True)
class GovernedProbabilityDecision:
    """Sport-aware governed probability decision shared by runtime consumers."""

    sport: str
    probability_source: str
    evidence_state: str
    governance_status: str
    sizing_eligible: bool
    descriptive_only_flag: bool
    excluded_from_approval_flag: bool
    abstain: bool
    abstention_reason: Optional[str]
    evidence_state_reason: str
    evidence_state_source_artifact: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "probability_source": self.probability_source,
            "evidence_state": self.evidence_state,
            "governance_status": self.governance_status,
            "sizing_eligible": self.sizing_eligible,
            "descriptive_only_flag": self.descriptive_only_flag,
            "excluded_from_approval_flag": self.excluded_from_approval_flag,
            "abstain": self.abstain,
            "abstention_reason": self.abstention_reason,
            "evidence_state_reason": self.evidence_state_reason,
            "evidence_state_source_artifact": self.evidence_state_source_artifact,
        }


def publish_governed_probability_decision(
    sport: str,
    *,
    probability_source: str,
    evidence_state_source_artifact: Optional[str] = None,
    abstain: bool = False,
    abstention_reason: Optional[str] = None,
    evidence_state_reason: Optional[str] = None,
) -> GovernedProbabilityDecision:
    """Project sport-validation publication into runtime probability metadata."""

    from plugins.sport_validation import can_size_from_validation_state, publish_sport_validation_state

    state = publish_sport_validation_state(sport.upper())
    evidence_state = state["validation_status"]
    runtime_parity = state["runtime_parity"]
    blockers = state["approval_blockers"]
    blocker_codes = (
        list(blockers["missing_evidence"])
        + list(blockers["contamination"])
        + list(blockers["parity_failures"])
    )
    default_reason = (
        evidence_state_reason
        or abstention_reason
        or ", ".join(blocker_codes)
        or f"{sport.upper()} remains {evidence_state} pending governed evidence."
    )
    governance_status = "candidate_ready" if evidence_state == "candidate" else "descriptive_only"
    sizing_eligible = (
        (not abstain)
        and runtime_parity.get("status") == "aligned"
        and can_size_from_validation_state(state)
    )
    artifact_ref = (
        evidence_state_source_artifact
        or state["artifact_provenance"].get("artifact_id")
        or "governed_validation_publication"
    )
    return GovernedProbabilityDecision(
        sport=sport.upper(),
        probability_source=probability_source,
        evidence_state=evidence_state,
        governance_status=governance_status,
        sizing_eligible=sizing_eligible,
        descriptive_only_flag=not sizing_eligible,
        excluded_from_approval_flag=not sizing_eligible,
        abstain=abstain,
        abstention_reason=abstention_reason,
        evidence_state_reason=default_reason,
        evidence_state_source_artifact=artifact_ref,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _logit(p: float) -> float:
    """Logit transform: log(p / (1 - p)), clipped for numerical stability."""
    p = max(min(p, 1.0 - 1e-15), 1e-15)
    return math.log(p / (1.0 - p))


def _raw_to_calibrated(raw_prob: float, model: LogisticRegression) -> float:
    """Apply a fitted Platt logistic regression to a raw probability.

    Args:
        raw_prob: Raw Elo probability in [0, 1].
        model: Fitted LogisticRegression with a single feature.

    Returns:
        Calibrated probability in (0, 1).
    """
    logit_val = _logit(raw_prob)
    X = np.array([[logit_val]])
    prob_pos = model.predict_proba(X)[0, 1]
    return float(prob_pos)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ProbabilityCalibrator:
    """Per-sport Platt scaling calibrator for Elo win probabilities.

    Fits a logistic regression per sport on historical (elo_prob, actual_outcome)
    pairs from the ``placed_bets`` and ``bet_recommendations`` tables.
    Calibrated probabilities preserve monotonicity and stay within (0, 1).

    Typical usage::

        calibrator = ProbabilityCalibrator()
        calibrator.fit("MLB")
        calibrated = calibrator.calibrate("MLB", raw_elo_prob)
    """

    def __init__(self, db: Optional[DBManager] = None, load_precomputed: bool = True) -> None:
        """Initialise the calibrator.

        Args:
            db: Database manager.  Defaults to the global ``default_db``.
            load_precomputed: If True, load pre-computed Platt coefficients from
                ``data/calibration/recalculated_platt.json`` on startup. Disable
                when you want to test purely DB-trained behaviour.
        """
        self.db = db or default_db
        self._models: dict[str, LogisticRegression] = {}
        if load_precomputed:
            self._load_recalculated_coefficients()

    def _load_recalculated_coefficients(self) -> None:
        """Load pre-computed Platt coefficients from disk if available."""
        path = "data/calibration/recalculated_platt.json"
        if not os.path.exists(path):
            return

        try:
            with open(path, "r") as f:
                coeffs = json.load(f)

            for sport, data in coeffs.items():
                # Reconstruct LogisticRegression model from A and B
                # P(win) = 1 / (1 + exp(A * logit + B))
                # Scikit-learn LR uses: 1 / (1 + exp(-(coef * x + intercept)))
                # So: -(coef * x + intercept) = A * x + B
                # coef = -A, intercept = -B
                model = LogisticRegression()
                model.coef_ = np.array([[-data["A"]]])
                model.intercept_ = np.array([-data["B"]])
                model.classes_ = np.array([0.0, 1.0])
                self._models[sport.upper()] = model
                self._models[sport.lower()] = model
        except Exception as e:
            print(f"⚠️  Could not load recalculated calibration: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calibrate(self, sport: str, elo_prob: float) -> float:
        """Apply Platt scaling to a raw Elo probability.

        Args:
            sport: Sport name (e.g. ``"MLB"``, ``"EPL"``, ``"TENNIS"``).
                Must match the sport used in ``fit()``.
            elo_prob: Raw Elo-predicted win probability in **[0, 1]**.

        Returns:
            Calibrated probability in **[0, 1]**.

        Raises:
            CalibratorNotFittedError: If no model is fitted for *sport*.
        """
        sport_upper = sport.upper()
        if sport_upper not in self._models:
            raise CalibratorNotFittedError(sport_upper)
        model = self._models[sport_upper]
        return _raw_to_calibrated(elo_prob, model)

    def fit(self, sport: str, force_retrain: bool = False, limit_to_placed_bets: bool = False) -> None:
        """Fit (or refit) a Platt calibration model for a sport.

        Fetches historical (elo_prob, outcome) pairs from both the ``placed_bets``
        and ``bet_recommendations`` tables.

        Args:
            sport: Sport to fit (e.g. ``"MLB"``).
            force_retrain: If ``True``, discard any cached model and refit.
            limit_to_placed_bets: If ``True``, only use data from actual placed bets.

        Raises:
            CalibratorNotFittedError: If fewer than MIN_BETS_FOR_FIT samples are
                available for *sport*.
        """
        sport_upper = sport.upper()
        if sport_upper in self._models and not force_retrain:
            return  # Already fitted, nothing to do.

        X, y = self._fetch_training_data(self.db, sport_upper, limit_to_placed_bets)
        if len(X) < MIN_BETS_FOR_FIT:
            raise CalibratorNotFittedError(
                f"{sport_upper}: only {len(X)} settled samples available "
                f"(need {MIN_BETS_FOR_FIT})"
            )

        model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=500, random_state=42)
        model.fit(X, y)
        self._models[sport_upper] = model

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_training_data(
        db: DBManager, sport: str, limit_to_placed_bets: bool = False
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Fetch (elo_prob, outcome) pairs from settled bets and recommendations.

        Args:
            db: Database manager to query.
            sport: Sport to fetch data for.
            limit_to_placed_bets: Only use actual placed bets.

        Returns:
            A tuple ``(X, y)`` where ``X`` is a 2D array of logit-transformed
            Elo probabilities, and ``y`` is a 1D array of binary outcomes.
        """
        sport_upper = sport.upper()

        # Part 1: Placed Bets (canonical source)
        placed_query = """
            SELECT elo_prob,
                   CASE WHEN status = 'won' THEN 1.0 ELSE 0.0 END AS outcome
            FROM placed_bets
            WHERE UPPER(sport) = :sport
              AND status IN ('won', 'lost')
              AND elo_prob IS NOT NULL
        """

        placed_df = pd.DataFrame()
        try:
            placed_df = db.fetch_df(placed_query, {"sport": sport_upper})
        except Exception:
            pass

        if limit_to_placed_bets:
            df = placed_df
        else:
            # Part 2: Recommendations (augmentation source)
            # We match in Python to handle name mapping more flexibly.
            recs_query = """
                SELECT elo_prob, home_team, away_team, recommendation_date
                FROM bet_recommendations
                WHERE UPPER(sport) = :sport
                  AND elo_prob IS NOT NULL
                  AND recommendation_date < CURRENT_DATE
            """

            games_query = """
                SELECT home_team_name, away_team_name, game_date, home_score, away_score
                FROM unified_games
                WHERE UPPER(sport) = :sport
                  AND home_score IS NOT NULL
                  AND away_score IS NOT NULL
                  AND game_date < CURRENT_DATE
            """

            try:
                recs_df = db.fetch_df(recs_query, {"sport": sport_upper})
                games_df = db.fetch_df(games_query, {"sport": sport_upper})

                if recs_df is not None and not recs_df.empty and games_df is not None and not games_df.empty:
                    from plugins.naming_resolver import NamingResolver, NamingContext

                    # Normalize names in both DFs for matching
                    def normalize(name):
                        ctx = NamingContext(sport=sport_upper.lower(), source="kalshi", name=name)
                        return NamingResolver.resolve(ctx).lower()

                    def normalize_elo(name):
                        ctx = NamingContext(sport=sport_upper.lower(), source="elo", name=name)
                        return NamingResolver.resolve(ctx).lower()

                    recs_df["h_norm"] = recs_df["home_team"].apply(normalize)
                    recs_df["a_norm"] = recs_df["away_team"].apply(normalize)

                    games_df["h_norm"] = games_df["home_team_name"].apply(normalize_elo)
                    games_df["a_norm"] = games_df["away_team_name"].apply(normalize_elo)

                    # Join on normalized names and date
                    merged = pd.merge(
                        recs_df,
                        games_df,
                        left_on=["h_norm", "a_norm", "recommendation_date"],
                        right_on=["h_norm", "a_norm", "game_date"]
                    )

                    if not merged.empty:
                        merged["outcome"] = (merged["home_score"] > merged["away_score"]).astype(float)
                        recs_calib_df = merged[["elo_prob", "outcome"]]

                        if placed_df is not None and not placed_df.empty:
                            df = pd.concat([placed_df, recs_calib_df], ignore_index=True)
                        else:
                            df = recs_calib_df
                    else:
                        df = placed_df
                else:
                    df = placed_df
            except Exception:
                df = placed_df

        if df is not None and not df.empty:
            # Drop duplicates if any overlap (same elo_prob and outcome)
            df = df.drop_duplicates()

        if df is None or df.empty:
            return np.empty((0, 1), dtype=np.float64), np.empty((0,), dtype=np.float64)

        elo_probs = df["elo_prob"].to_numpy(dtype=np.float64)
        outcomes = df["outcome"].to_numpy(dtype=np.float64)

        # Logit-transform requires p in (0, 1)
        elo_probs = np.clip(elo_probs, 1e-6, 1.0 - 1e-6)

        # Logit-transform the feature
        logits = np.array(
            [_logit(p) for p in elo_probs], dtype=np.float64
        ).reshape(-1, 1)

        return logits, outcomes
