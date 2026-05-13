"""EPL probability ensemble built on honest pre-match features.

The EPL betting pipeline historically relied on plain Elo probabilities. This
module adds a lightweight probabilistic layer that combines:

1. Elo 3-way probabilities
2. Rolling team form / goals-for / goals-against features
3. Bookmaker implied probabilities

The model is intentionally simple and fast to train so it can bootstrap itself
from the football-data.co.uk season CSVs when no persisted model exists.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import logging
from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from plugins.epl_games import EPLGames
from plugins.elo.epl_elo_rating import EPLEloRating

logger = logging.getLogger(__name__)

_BOOKMAKER_COLUMN_SETS: tuple[tuple[str, str, str], ...] = (
    ("PSCH", "PSCD", "PSCA"),
    ("AvgCH", "AvgCD", "AvgCA"),
    ("B365H", "B365D", "B365A"),
    ("AvgH", "AvgD", "AvgA"),
    ("MaxH", "MaxD", "MaxA"),
)

_DEFAULT_BOOKMAKER_PROBS: dict[str, float] = {
    "home": 0.45,
    "draw": 0.25,
    "away": 0.30,
}

_DEFAULT_FEATURE_VALUES: dict[str, float] = {
    "home_form": 0.5,
    "away_form": 0.5,
    "home_avg_gf": 1.4,
    "away_avg_gf": 1.2,
    "home_avg_ga": 1.2,
    "away_avg_ga": 1.4,
    "bookmaker_prob_home": _DEFAULT_BOOKMAKER_PROBS["home"],
    "bookmaker_prob_draw": _DEFAULT_BOOKMAKER_PROBS["draw"],
    "bookmaker_prob_away": _DEFAULT_BOOKMAKER_PROBS["away"],
}


def _parse_match_dates(series: pd.Series) -> pd.Series:
    """Parse football-data.co.uk dates without inference warnings."""
    parsed = pd.to_datetime(series, format="%d/%m/%Y", dayfirst=True, errors="coerce")
    missing_mask = parsed.isna()
    if missing_mask.any():
        parsed.loc[missing_mask] = pd.to_datetime(
            series.loc[missing_mask],
            format="%d/%m/%y",
            dayfirst=True,
            errors="coerce",
        )
    return parsed


def _normalize_probabilities(
    away_prob: float,
    draw_prob: float,
    home_prob: float,
) -> np.ndarray:
    """Return normalized [away, draw, home] probabilities."""
    probs = np.array([away_prob, draw_prob, home_prob], dtype=float)
    probs = np.clip(probs, 1e-6, None)
    probs /= probs.sum()
    return probs


def _bookmaker_probabilities_from_row(row: pd.Series) -> dict[str, float]:
    """Extract normalized bookmaker implied probabilities from a raw CSV row."""
    for home_col, draw_col, away_col in _BOOKMAKER_COLUMN_SETS:
        if all(column in row.index for column in (home_col, draw_col, away_col)):
            values = [row[home_col], row[draw_col], row[away_col]]
            if all(pd.notna(value) and float(value) > 1.0 for value in values):
                inverse = np.array(
                    [1.0 / float(value) for value in values], dtype=float
                )
                inverse /= inverse.sum()
                return {
                    "home": float(inverse[0]),
                    "draw": float(inverse[1]),
                    "away": float(inverse[2]),
                }
    return dict(_DEFAULT_BOOKMAKER_PROBS)


@dataclass
class EPLEnsembleModel:
    """Production EPL probability ensemble.

    Attributes:
        model_dir: Directory where the fitted model artifact is stored.
        auto_train: Whether to train from CSVs automatically when no model is
            present on disk.
        model: Fitted multinomial classifier.
        scaler: Feature scaler used during training and prediction.
        features: Ordered feature list expected by the classifier.
        is_trained: Whether a trained artifact has been loaded or fitted.
    """

    model_dir: str = "data/models/epl"
    auto_train: bool = True
    model: LogisticRegression | None = None
    scaler: StandardScaler | None = None
    features: list[str] = field(
        default_factory=lambda: [
            "elo_prob_home",
            "elo_prob_draw",
            "elo_prob_away",
            "elo_diff",
            "home_form",
            "away_form",
            "home_avg_gf",
            "away_avg_gf",
            "home_avg_ga",
            "away_avg_ga",
            "bookmaker_prob_home",
            "bookmaker_prob_draw",
            "bookmaker_prob_away",
        ]
    )
    is_trained: bool = False
    ml_weight: float = 0.70
    bookmaker_weight: float = 0.30
    classes_: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure the model directory exists."""
        Path(self.model_dir).mkdir(parents=True, exist_ok=True)

    @property
    def artifact_path(self) -> Path:
        """Return the pickle path for the persisted ensemble."""
        return Path(self.model_dir) / "model.pkl"

    def load(self) -> bool:
        """Load a persisted ensemble artifact if it exists."""
        if not self.artifact_path.exists():
            return False

        with self.artifact_path.open("rb") as handle:
            payload = pickle.load(handle)

        self.model = payload["model"]
        self.scaler = payload["scaler"]
        self.features = payload["features"]
        self.is_trained = bool(payload["is_trained"])
        self.classes_ = list(payload.get("classes_", []))
        return self.is_trained

    def save(self) -> None:
        """Persist the fitted ensemble artifact."""
        if self.model is None or self.scaler is None:
            raise ValueError("Cannot save an ensemble before fitting it")

        payload = {
            "model": self.model,
            "scaler": self.scaler,
            "features": self.features,
            "is_trained": self.is_trained,
            "classes_": self.classes_,
        }
        with self.artifact_path.open("wb") as handle:
            pickle.dump(payload, handle)

    def ensure_trained(self, data_dir: str = "data/epl") -> bool:
        """Load an existing model or train a fresh one if configured to do so."""
        if self.load():
            return True
        if not self.auto_train:
            return False

        try:
            self.train_from_csvs(data_dir=data_dir)
            self.save()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("⚠️ Failed to train EPL ensemble model: %s", exc)
            return False

    def train_from_csvs(self, data_dir: str = "data/epl") -> None:
        """Train the ensemble from football-data.co.uk EPL CSVs."""
        feature_frame = self.build_training_frame(data_dir=data_dir)
        if feature_frame.empty:
            raise ValueError("No EPL training rows available")

        x_train = feature_frame[self.features]
        y_train = feature_frame["target"]

        self.scaler = StandardScaler()
        x_scaled = self.scaler.fit_transform(x_train)

        self.model = LogisticRegression(max_iter=2000, solver="lbfgs")
        self.model.fit(x_scaled, y_train)
        self.classes_ = [int(value) for value in getattr(self.model, "classes_", [])]
        self.is_trained = True

    def build_training_frame(self, data_dir: str = "data/epl") -> pd.DataFrame:
        """Build an honest pre-match feature frame from historical CSVs."""
        epl_games = EPLGames(data_dir=data_dir)
        epl_games.download_games()

        csv_paths = sorted(Path(data_dir).glob("E0_*.csv"))
        if not csv_paths:
            raise FileNotFoundError(f"No EPL CSV files found in {data_dir}")

        raw_df = pd.concat(
            [pd.read_csv(csv_path) for csv_path in csv_paths],
            ignore_index=True,
        )
        raw_df["Date"] = _parse_match_dates(raw_df["Date"])
        raw_df = raw_df.dropna(
            subset=["Date", "HomeTeam", "AwayTeam", "FTR", "FTHG", "FTAG"]
        ).copy()
        raw_df = raw_df[raw_df["FTR"].isin(["H", "D", "A"])].copy()
        raw_df["Date"] = pd.to_datetime(raw_df["Date"])
        raw_df["FTHG"] = raw_df["FTHG"].astype(float)
        raw_df["FTAG"] = raw_df["FTAG"].astype(float)
        raw_df = raw_df.sort_values("Date").reset_index(drop=True)

        elo = EPLEloRating()

        from plugins.probability_calibration import ProbabilityCalibrator
        from plugins.db_manager import default_db
        calibrator = ProbabilityCalibrator(db=default_db)
        calibrator.fit("epl")

        team_points_form: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=5))
        team_goals_for: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=5))
        team_goals_against: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=5)
        )
        training_rows: list[dict[str, Any]] = []

        for game in raw_df.itertuples(index=False):
            home_team = str(game.HomeTeam)
            away_team = str(game.AwayTeam)

            home_prob, draw_prob, away_prob = elo.predict_probs(home_team, away_team)

            # Apply calibration to features
            try:
                home_prob = calibrator.calibrate("epl", home_prob)
                rem = 1.0 - home_prob
                total_rem = draw_prob + away_prob
                if total_rem > 0:
                    draw_prob = (draw_prob / total_rem) * rem
                    away_prob = (away_prob / total_rem) * rem
            except: pass

            bookmaker_probs = _bookmaker_probabilities_from_row(
                pd.Series(game._asdict())
            )

            training_rows.append(
                {
                    "target": {"A": 0, "D": 1, "H": 2}[str(game.FTR)],
                    "elo_prob_home": home_prob,
                    "elo_prob_draw": draw_prob,
                    "elo_prob_away": away_prob,
                    "elo_diff": elo.get_rating(home_team) - elo.get_rating(away_team),
                    "home_form": _mean_or_default(
                        team_points_form[home_team],
                        _DEFAULT_FEATURE_VALUES["home_form"],
                    ),
                    "away_form": _mean_or_default(
                        team_points_form[away_team],
                        _DEFAULT_FEATURE_VALUES["away_form"],
                    ),
                    "home_avg_gf": _mean_or_default(
                        team_goals_for[home_team],
                        _DEFAULT_FEATURE_VALUES["home_avg_gf"],
                    ),
                    "away_avg_gf": _mean_or_default(
                        team_goals_for[away_team],
                        _DEFAULT_FEATURE_VALUES["away_avg_gf"],
                    ),
                    "home_avg_ga": _mean_or_default(
                        team_goals_against[home_team],
                        _DEFAULT_FEATURE_VALUES["home_avg_ga"],
                    ),
                    "away_avg_ga": _mean_or_default(
                        team_goals_against[away_team],
                        _DEFAULT_FEATURE_VALUES["away_avg_ga"],
                    ),
                    "bookmaker_prob_home": bookmaker_probs["home"],
                    "bookmaker_prob_draw": bookmaker_probs["draw"],
                    "bookmaker_prob_away": bookmaker_probs["away"],
                }
            )

            home_goals = float(game.FTHG)
            away_goals = float(game.FTAG)
            if home_goals > away_goals:
                home_points = 1.0
                away_points = 0.0
            elif away_goals > home_goals:
                home_points = 0.0
                away_points = 1.0
            else:
                home_points = 0.5
                away_points = 0.5

            team_points_form[home_team].append(home_points)
            team_points_form[away_team].append(away_points)
            team_goals_for[home_team].append(home_goals)
            team_goals_for[away_team].append(away_goals)
            team_goals_against[home_team].append(away_goals)
            team_goals_against[away_team].append(home_goals)

            elo.legacy_update(home_team, away_team, str(game.FTR))

        return pd.DataFrame(training_rows)

    def predict_probs(self, features: dict[str, float]) -> dict[str, float]:
        """Predict Home/Draw/Away probabilities from pre-match features."""
        ordered_features = {
            feature: float(
                features.get(feature, _DEFAULT_FEATURE_VALUES.get(feature, 0.0))
            )
            for feature in self.features
        }

        if not self.is_trained or self.model is None or self.scaler is None:
            return self._fallback_probabilities(ordered_features)

        feature_frame = pd.DataFrame([ordered_features], columns=self.features)
        scaled = self.scaler.transform(feature_frame)
        model_probs = self.model.predict_proba(scaled)[0]

        away_draw_home = np.zeros(3, dtype=float)
        classes = self.classes_ or [int(value) for value in self.model.classes_]
        for index, cls in enumerate(classes):
            away_draw_home[int(cls)] = float(model_probs[index])

        bookmaker_probs = np.array(
            [
                ordered_features["bookmaker_prob_away"],
                ordered_features["bookmaker_prob_draw"],
                ordered_features["bookmaker_prob_home"],
            ],
            dtype=float,
        )
        blended = (
            self.ml_weight * away_draw_home + self.bookmaker_weight * bookmaker_probs
        )
        normalized = _normalize_probabilities(blended[0], blended[1], blended[2])
        return {
            "home": float(normalized[2]),
            "draw": float(normalized[1]),
            "away": float(normalized[0]),
        }

    def _fallback_probabilities(
        self, ordered_features: dict[str, float]
    ) -> dict[str, float]:
        """Fallback blend used when no trained artifact is available."""
        elo_probs = np.array(
            [
                ordered_features["elo_prob_away"],
                ordered_features["elo_prob_draw"],
                ordered_features["elo_prob_home"],
            ],
            dtype=float,
        )
        bookmaker_probs = np.array(
            [
                ordered_features["bookmaker_prob_away"],
                ordered_features["bookmaker_prob_draw"],
                ordered_features["bookmaker_prob_home"],
            ],
            dtype=float,
        )
        normalized = _normalize_probabilities(
            *(0.70 * bookmaker_probs + 0.30 * elo_probs)
        )
        return {
            "home": float(normalized[2]),
            "draw": float(normalized[1]),
            "away": float(normalized[0]),
        }


def _mean_or_default(values: deque[float], default: float) -> float:
    """Return the mean of a deque or a deterministic fallback."""
    if not values:
        return default
    return float(np.mean(values))
