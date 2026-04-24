"""
Improved Ligue1 backtesting with feature engineering and ensemble methods.
Targets 5%+ accuracy improvement (54.5% -> 59.5%+).
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
from pathlib import Path
import sys
import argparse

class Ligue1Predictor:
    """Enhanced Ligue1 predictor with ensemble methods."""

    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.feature_cols = None
        self.team_elos = {}
        self.default_elo = 1500

    def load_data(self, data_dir="data/ligue1"):
        """Load and prepare Ligue1 data."""
        csv_files = sorted(Path(data_dir).glob("F1_*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {data_dir}")

        df_list = []
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            df['source_file'] = csv_file.name
            df_list.append(df)

        df = pd.concat(df_list, ignore_index=True)
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)

        print(f"Loaded {len(df)} games")
        return df

    def compute_elo_ratings(self, df):
        """Compute ELO ratings sequentially."""
        teams = set(df['HomeTeam'].unique()) | set(df['AwayTeam'].unique())
        self.team_elos = {team: self.default_elo for team in teams}

        home_elo = []
        away_elo = []
        elo_diff = []

        for _, game in df.iterrows():
            home = game['HomeTeam']
            away = game['AwayTeam']

            home_rating = self.team_elos[home]
            away_rating = self.team_elos[away]

            home_elo.append(home_rating)
            away_elo.append(away_rating)
            elo_diff.append(home_rating - away_rating)

            # Update ratings based on result
            home_goals = game['FTHG']
            away_goals = game['FTAG']

            # Expected scores
            exp_home = 1 / (1 + 10 ** ((away_rating - home_rating) / 400))
            exp_away = 1 - exp_home

            # Actual score (with draw)
            if home_goals > away_goals:
                actual_home = 1.0
                actual_away = 0.0
                k = 30
            elif home_goals < away_goals:
                actual_home = 0.0
                actual_away = 1.0
                k = 30
            else:
                actual_home = 0.5
                actual_away = 0.5
                k = 20  # Smaller adjustment for draws

            # Update
            self.team_elos[home] = home_rating + k * (actual_home - exp_home)
            self.team_elos[away] = away_rating + k * (actual_away - exp_away)

        df = df.copy()
        df['home_elo'] = home_elo
        df['away_elo'] = away_elo
        df['elo_diff'] = elo_diff
        df['elo_prob_home'] = df.apply(
            lambda r: 1 / (1 + 10 ** ((r['away_elo'] - r['home_elo']) / 400)),
            axis=1
        )
        df['elo_prob_away'] = df.apply(
            lambda r: 1 / (1 + 10 ** ((r['home_elo'] - r['away_elo']) / 400)),
            axis=1
        )
        df['elo_prob_draw'] = 1 - df['elo_prob_home'] - df['elo_prob_away']
        df['elo_prob_draw'] = df['elo_prob_draw'].clip(0.15, 0.5)  # Bounds for draw

        return df

    def add_team_form(self, df, window=5):
        """Add team form features."""
        df = df.copy()

        for idx, game in df.iterrows():
            home = game['HomeTeam']
            away = game['AwayTeam']
            date = game['Date']

            # Home team history
            home_hist = df[(df['Date'] < date) &
                          ((df['HomeTeam'] == home) | (df['AwayTeam'] == home))]
            home_recent = home_hist.tail(window)

            home_wins = 0
            home_goals_for = []
            home_goals_against = []

            for _, g in home_recent.iterrows():
                if g['HomeTeam'] == home:
                    gf = g['FTHG']
                    ga = g['FTAG']
                else:
                    gf = g['FTAG']
                    ga = g['FTHG']

                home_goals_for.append(gf)
                home_goals_against.append(ga)

                if gf > ga:
                    home_wins += 1
                elif gf == ga:
                    home_wins += 0.5

            df.at[idx, 'home_form'] = home_wins / len(home_recent) if len(home_recent) > 0 else 0.5
            df.at[idx, 'home_avg_gf'] = np.mean(home_goals_for) if home_goals_for else 1.0
            df.at[idx, 'home_avg_ga'] = np.mean(home_goals_against) if home_goals_against else 1.0

            # Away team history
            away_hist = df[(df['Date'] < date) &
                          ((df['HomeTeam'] == away) | (df['AwayTeam'] == away))]
            away_recent = away_hist.tail(window)

            away_wins = 0
            away_goals_for = []
            away_goals_against = []

            for _, g in away_recent.iterrows():
                if g['HomeTeam'] == away:
                    gf = g['FTHG']
                    ga = g['FTAG']
                else:
                    gf = g['FTAG']
                    ga = g['FTHG']

                away_goals_for.append(gf)
                away_goals_against.append(ga)

                if gf > ga:
                    away_wins += 1
                elif gf == ga:
                    away_wins += 0.5

            df.at[idx, 'away_form'] = away_wins / len(away_recent) if len(away_recent) > 0 else 0.5
            df.at[idx, 'away_avg_gf'] = np.mean(away_goals_for) if away_goals_for else 1.0
            df.at[idx, 'away_avg_ga'] = np.mean(away_goals_against) if away_goals_against else 1.0

        return df

    def get_feature_columns(self):
        """Define feature columns for ML model."""
        return [
            'HS', 'AS', 'HST', 'AST',  # Shots
            'HF', 'AF', 'HC', 'AC',  # Fouls and corners
            'HY', 'AY', 'HR', 'AR',  # Cards
            'home_form', 'away_form',  # Form
            'home_avg_gf', 'home_avg_ga',  # Goals for/against
            'away_avg_gf', 'away_avg_ga',
            'home_elo', 'away_elo', 'elo_diff',  # ELO
            # Shot accuracy
            'shot_diff', 'shot_on_target_diff',
            # Bookmaker odds (converted to probabilities)
            'bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away'
        ]

    def prepare_features(self, df):
        """Prepare feature matrix."""
        df = df.copy()

        # Shot-based features
        df['shot_diff'] = df.apply(
            lambda r: (r['HS'] - r['AS']) if not pd.isna(r['HS']) and not pd.isna(r['AS']) else 0,
            axis=1
        )
        df['shot_on_target_diff'] = df.apply(
            lambda r: (r['HST'] - r['AST']) if not pd.isna(r['HST']) and not pd.isna(r['AST']) else 0,
            axis=1
        )

        # Bookmaker probabilities from average odds
        df['bookmaker_prob_home'] = df.apply(
            lambda r: (1/r['AvgH']) / ((1/r['AvgH']) + (1/r['AvgD']) + (1/r['AvgA']))
            if r['AvgH'] > 0 else 0.4,
            axis=1
        )
        df['bookmaker_prob_draw'] = df.apply(
            lambda r: (1/r['AvgD']) / ((1/r['AvgH']) + (1/r['AvgD']) + (1/r['AvgA']))
            if r['AvgD'] > 0 else 0.25,
            axis=1
        )
        df['bookmaker_prob_away'] = df.apply(
            lambda r: (1/r['AvgA']) / ((1/r['AvgH']) + (1/r['AvgD']) + (1/r['AvgA']))
            if r['AvgA'] > 0 else 0.35,
            axis=1
        )

        feature_cols = self.get_feature_columns()

        # Fill NaN values
        X = df[feature_cols].fillna(0)

        # Target
        y = df['FTR'].map({'H': 0, 'D': 1, 'A': 2})

        return X, y, feature_cols

    def train(self, df, test_size=0.3):
        """Train ensemble models."""
        print("Computing ELO ratings...")
        df = self.compute_elo_ratings(df)

        print("Computing team form...")
        df = self.add_team_form(df)

        # Split data chronologically
        split_idx = int(len(df) * (1 - test_size))
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        print(f"Train samples: {len(train_df)}")
        print(f"Test samples: {len(test_df)}")

        # Prepare features
        X_train, y_train, self.feature_cols = self.prepare_features(train_df)
        X_test, y_test, _ = self.prepare_features(test_df)

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        print("Training models...")

        # XGBoost
        print("  XGBoost...")
        xgb_model = xgb.XGBClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=6,
            random_state=42,
            objective='multi:softprob',
            num_class=3,
            eval_metric='mlogloss'
        )
        xgb_model.fit(X_train_scaled, y_train)
        self.models['xgboost'] = xgb_model

        # LightGBM
        print("  LightGBM...")
        lgb_model = lgb.LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=6,
            random_state=42,
            objective='multiclass',
            num_class=3,
            verbose=-1
        )
        lgb_model.fit(X_train_scaled, y_train)
        self.models['lightgbm'] = lgb_model

        # Gradient Boosting
        print("  GradientBoosting...")
        gb_model = GradientBoostingClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=6,
            random_state=42
        )
        gb_model.fit(X_train_scaled, y_train)
        self.models['gradient_boosting'] = gb_model

        return train_df, test_df, X_test_scaled, y_test

    def predict_proba(self, X, elo_probs=None, bookie_probs=None):
        """Ensemble prediction with blending."""
        n_samples = len(X)
        n_classes = 3

        # ML predictions (average of all models)
        ml_probs = np.zeros((n_samples, n_classes))

        for name, model in self.models.items():
            probs = model.predict_proba(X)
            ml_probs += probs

        ml_probs /= len(self.models)

        # Blend with ELO and Bookmaker
        final_probs = ml_probs * 0.6  # 60% ML

        if elo_probs is not None:
            final_probs += elo_probs * 0.2  # 20% ELO

        if bookie_probs is not None:
            final_probs += bookie_probs * 0.2  # 20% Bookmaker

        # Normalize
        final_probs = final_probs / final_probs.sum(axis=1, keepdims=True)

        return final_probs

    def evaluate(self, df, X_test_scaled, y_true, label="Model"):
        """Evaluate model performance."""
        # Get ELO probabilities
        elo_probs = df[['elo_prob_home', 'elo_prob_draw', 'elo_prob_away']].values

        # Get Bookmaker probabilities
        bookie_probs = df[['bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away']].values

        # Ensemble prediction
        probs = self.predict_proba(X_test_scaled, elo_probs, bookie_probs)
        y_pred = np.argmax(probs, axis=1)

        accuracy = accuracy_score(y_true, y_pred)
        ll = log_loss(y_true, probs, labels=[0, 1, 2])

        print(f"\n{label} Results:")
        print(f"  Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
        print(f"  Log Loss: {ll:.4f}")

        # Per-class accuracy
        for cls, name in enumerate(['Home', 'Draw', 'Away']):
            mask = y_true == cls
            if mask.sum() > 0:
                cls_acc = (y_pred[mask] == cls).sum() / mask.sum()
                print(f"  {name} Accuracy: {cls_acc:.4f} ({mask.sum()} samples)")

        # Confusion-like stats
        print(f"  Predicted Home: {(y_pred == 0).sum()}")
        print(f"  Predicted Draw: {(y_pred == 1).sum()}")
        print(f"  Predicted Away: {(y_pred == 2).sum()}")

        return accuracy, ll, probs

def main():
    parser = argparse.ArgumentParser(description='Ligue1 Prediction Improvement')
    parser.add_argument('--data_dir', default='data/ligue1', help='Data directory')
    parser.add_argument('--output', default='ligue1_results.csv', help='Output file')
    args = parser.parse_args()

    print("=" * 60)
    print("LIGUE1 PREDICTION ACCURACY IMPROVEMENT")
    print("=" * 60)

    predictor = Ligue1Predictor()

    # Load data
    print("\nLoading data...")
    df = predictor.load_data(args.data_dir)

    # Train and evaluate
    print("\nTraining models...")
    train_df, test_df, X_test_scaled, y_test = predictor.train(df)

    # Evaluate
    print("\n" + "=" * 60)
    print("TEST SET EVALUATION")
    print("=" * 60)

    # Baseline: Pure ELO
    elo_probs = test_df[['elo_prob_home', 'elo_prob_draw', 'elo_prob_away']].values
    elo_pred = np.argmax(elo_probs, axis=1)
    baseline_acc = accuracy_score(y_test.values, elo_pred)
    print(f"\nPure ELO (Baseline) Results:")
    print(f"  Accuracy: {baseline_acc:.4f} ({baseline_acc*100:.2f}%)")

    # Bookmaker consensus
    bookie_probs = test_df[['bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away']].values
    bookie_pred = np.argmax(bookie_probs, axis=1)
    bookie_acc = accuracy_score(y_test.values, bookie_pred)
    print(f"\nBookmaker Consensus Results:")
    print(f"  Accuracy: {bookie_acc:.4f} ({bookie_acc*100:.2f}%)")

    # Ensemble
    acc, ll, probs = predictor.evaluate(test_df, X_test_scaled, y_test.values, "ENSEMBLE (ELO+ML+Bookmaker)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Baseline (Pure ELO): {baseline_acc*100:.2f}%")
    print(f"Bookmaker Consensus: {bookie_acc*100:.2f}%")
    print(f"ENSEMBLE Model: {acc*100:.2f}%")
    print(f"Improvement over baseline: {(acc - baseline_acc)*100:.2f}%")
    print(f"Improvement over bookmaker: {(acc - bookie_acc)*100:.2f}%")

    target = 0.545 + 0.05  # 5% improvement over 54.5%
    if acc >= target:
        print(f"\n✓ SUCCESS: Achieved {target*100:.1f}%+ target!")
    else:
        print(f"\n✗ Need {(target - acc)*100:.2f}% more to reach target")

    # Save results
    results = test_df.copy()
    results['pred_home'] = probs[:, 0]
    results['pred_draw'] = probs[:, 1]
    results['pred_away'] = probs[:, 2]
    results['prediction'] = np.argmax(probs, axis=1).map({0: 'H', 1: 'D', 2: 'A'})
    results['correct'] = results['prediction'] == results['FTR']

    results.to_csv(args.output, index=False)
    print(f"\nResults saved to {args.output}")

    return acc

if __name__ == "__main__":
    acc = main()
    sys.exit(0 if acc >= 0.595 else 1)
