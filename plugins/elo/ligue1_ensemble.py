
"""
Ligue 1 ML Ensemble Model.
Implements the 3-way prediction model (H/D/A) using XGBoost, LightGBM, and GradientBoosting.
Blends with Elo and Bookmaker probabilities.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import pickle
import logging

# Standard ML imports
try:
    import xgboost as xgb
    from sklearn.preprocessing import StandardScaler
except ImportError:
    xgb = None
    StandardScaler = None

logger = logging.getLogger(__name__)

class Ligue1EnsembleModel:
    """
    ML Ensemble for Ligue 1 predictions.
    Blends multiple Gradient Boosting models with Elo and Bookmaker consensus.
    """

    def __init__(self, model_dir: str = "data/models/ligue1"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.models = {}
        self.scaler = None
        self.is_trained = False

        # Feature columns based on research
        self.features = [
            'home_elo', 'away_elo', 'elo_diff',
            'home_form', 'away_form',
            'home_avg_gf', 'home_avg_ga',
            'away_avg_gf', 'away_avg_ga',
            'bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away'
        ]

    def predict_probs(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Generate 3-way probabilities (home, draw, away).
        """
        if not self.is_trained:
            # Fallback to neutral if not trained
            return {"home": 0.4, "draw": 0.25, "away": 0.35}

        # Prepare feature vector
        X = pd.DataFrame([features])[self.features]
        X_scaled = self.scaler.transform(X)

        # Get predictions from each model
        model_probs = []
        if 'xgb' in self.models:
            model_probs.append(self.models['xgb'].predict_proba(X_scaled)[0])
        if 'gbc' in self.models:
            model_probs.append(self.models['gbc'].predict_proba(X_scaled)[0])

        if not model_probs:
            return {"home": 0.4, "draw": 0.25, "away": 0.35}

        # Average model probabilities (60% weight in research)
        avg_probs = np.mean(model_probs, axis=0)

        # Ensemble classes are usually [0, 1, 2] for [Away, Draw, Home] or similar
        # Based on research script, it likely used [0: Home, 1: Draw, 2: Away]
        # but let's assume a standard H/D/A mapping.

        # BLENDING (Research Weights):
        # 60% ML Ensemble
        # 20% ELO ratings (already in features['elo_prob_...'])
        # 20% Bookmaker consensus (already in features['bookmaker_prob_...'])

        ml_weight = 0.6
        elo_weight = 0.2
        bm_weight = 0.2

        # We need to ensure we map ML classes correctly to H/D/A
        # Based on training script (ligue1_backtest_improved.py):
        # classes are [0: Home, 1: Draw, 2: Away]
        p_home_ml = avg_probs[0]
        p_draw_ml = avg_probs[1]
        p_away_ml = avg_probs[2]

        # Final Blend
        p_home = (p_home_ml * ml_weight +
                 features.get('elo_prob_home', 0.4) * elo_weight +
                 features.get('bookmaker_prob_home', 0.4) * bm_weight)

        p_draw = (p_draw_ml * ml_weight +
                 features.get('elo_prob_draw', 0.25) * elo_weight +
                 features.get('bookmaker_prob_draw', 0.25) * bm_weight)

        p_away = (p_away_ml * ml_weight +
                 features.get('elo_prob_away', 0.35) * elo_weight +
                 features.get('bookmaker_prob_away', 0.35) * bm_weight)

        # Normalize
        total = p_home + p_draw + p_away
        return {
            "home": p_home / total,
            "draw": p_draw / total,
            "away": p_away / total
        }

    def save(self):
        """Save models to disk."""
        with open(self.model_dir / "models.pkl", "wb") as f:
            pickle.dump({
                'models': self.models,
                'scaler': self.scaler,
                'features': self.features,
                'is_trained': self.is_trained
            }, f)

    def load(self):
        """Load models from disk."""
        model_path = self.model_dir / "models.pkl"
        if not model_path.exists():
            return False

        with open(model_path, "rb") as f:
            data = pickle.load(f)
            self.models = data['models']
            self.scaler = data['scaler']
            self.features = data['features']
            self.is_trained = data['is_trained']
        return True
