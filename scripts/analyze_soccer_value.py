import pandas as pd
import glob
from pathlib import Path
import sys

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
from plugins.elo import EPLEloRating
from plugins.elo import Ligue1EloRating


def analyze_soccer_sharp_value(sport_code, league_name):
    print(f"\n⚽ Analyzing {league_name} Sharp Consensus Value...")

    # 1. Load data
    data_dir = Path(f"data/{sport_code.lower()}")
    files = glob.glob(str(data_dir / "*.csv"))
    all_dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, low_memory=False)
            required = [
                "HomeTeam",
                "AwayTeam",
                "FTR",
                "Date",
                "PSH",
                "PSD",
                "PSA",
                "AvgH",
                "AvgD",
                "AvgA",
            ]
            if all(col in df.columns for col in required):
                all_dfs.append(df[required])
        except Exception:
            continue

    if not all_dfs:
        print(f"❌ No valid data files found for {league_name}.")
        return

    df = pd.concat(all_dfs, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date", "FTR", "AvgH", "AvgD", "AvgA"])
    df = df.sort_values("Date")

    # Filter for numeric odds
    for col in ["PSH", "PSD", "PSA", "AvgH", "AvgD", "AvgA"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["PSH", "PSD", "PSA", "AvgH", "AvgD", "AvgA"])

    print(f"✓ Loaded {len(df)} games with complete odds data.")

    # 2. Elo Simulation
    if sport_code.upper() == "EPL":
        elo = EPLEloRating(k_factor=20, home_advantage=60)
    else:
        elo = Ligue1EloRating(k_factor=20, home_advantage=60)

    elo_probs_list = []
    for _, row in df.iterrows():
        probs = elo.predict_3way(row["HomeTeam"], row["AwayTeam"])
        elo_probs_list.append(probs)
        elo.update(row["HomeTeam"], row["AwayTeam"], row["FTR"])

    df["elo_prob_H"] = [p["home"] for p in elo_probs_list]
    df["elo_prob_D"] = [p["draw"] for p in elo_probs_list]
    df["elo_prob_A"] = [p["away"] for p in elo_probs_list]

    # 3. Calculate Vig-Free Probabilities
    def remove_vig_3way(h, d, a):
        inv_h, inv_d, inv_a = 1 / h, 1 / d, 1 / a
        sum_inv = inv_h + inv_d + inv_a
        return inv_h / sum_inv, inv_d / sum_inv, inv_a / sum_inv

    market_probs = df.apply(
        lambda x: remove_vig_3way(x["AvgH"], x["AvgD"], x["AvgA"]), axis=1
    )
    df["market_prob_H"] = [p[0] for p in market_probs]
    df["market_prob_D"] = [p[1] for p in market_probs]
    df["market_prob_A"] = [p[2] for p in market_probs]

    sharp_probs = df.apply(
        lambda x: remove_vig_3way(x["PSH"], x["PSD"], x["PSA"]), axis=1
    )
    df["sharp_prob_H"] = [p[0] for p in sharp_probs]
    df["sharp_prob_D"] = [p[1] for p in sharp_probs]
    df["sharp_prob_A"] = [p[2] for p in sharp_probs]

    # 4. Simulation
    threshold = 0.05
    strategies = [
        ("Base Elo vs Avg Market (Kalshi Proxy)", "elo_only"),
        ("Elo + Sharp Consensus (Confirmation)", "elo_sharp"),
        ("Kalshi Mispricing vs Sharp (Pure Value)", "sharp_value"),
    ]

    print(f"\n📈 {league_name} Simulation Results:")
    print(f"{'Strategy':<45} | {'ROI':<8} | {'Win Rate':<8} | {'Bets'}")
    print("-" * 80)

    for name, mode in strategies:
        total_payout = 0
        total_bets = 0
        num_wins = 0

        for _, row in df.iterrows():
            outcomes = [
                (
                    "H",
                    row["elo_prob_H"],
                    row["market_prob_H"],
                    row["sharp_prob_H"],
                    row["AvgH"],
                ),
                (
                    "D",
                    row["elo_prob_D"],
                    row["market_prob_D"],
                    row["sharp_prob_D"],
                    row["AvgD"],
                ),
                (
                    "A",
                    row["elo_prob_A"],
                    row["market_prob_A"],
                    row["sharp_prob_A"],
                    row["AvgA"],
                ),
            ]

            for side, elo_p, mark_p, sharp_p, odds in outcomes:
                bet = False
                if mode == "elo_only":
                    if elo_p - mark_p > threshold:
                        bet = True
                elif mode == "elo_sharp":
                    if (elo_p - mark_p > threshold) and (sharp_p > mark_p + 0.01):
                        bet = True
                elif mode == "sharp_value":
                    if sharp_p - mark_p > 0.01:
                        bet = True

                if bet:
                    total_bets += 1
                    if row["FTR"] == side:
                        total_payout += odds - 1
                        num_wins += 1
                    else:
                        total_payout -= 1

        if total_bets == 0:
            continue
        roi = total_payout / total_bets
        print(f"  {name:45} | {roi:7.2%} | {num_wins / total_bets:8.1%} | {total_bets}")


if __name__ == "__main__":
    analyze_soccer_sharp_value("EPL", "English Premier League")
    analyze_soccer_sharp_value("LIGUE1", "French Ligue 1")
