"""
Team-level Glicko-2 rating system for sports predictions.

Glicko-2 extends Elo with:
- Rating (r): Like Elo rating
- Rating Deviation (RD): Uncertainty/confidence in rating
- Volatility (σ): Consistency of performance over time

Advantages over Elo:
- Handles rating uncertainty (RD decreases with more games)
- Volatility tracks if team is improving or declining
- More accurate probability estimates
"""

import math
from typing import Dict, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict

# Glicko-2 system constants
GLICKO_OFFSET = 1500.0
GLICKO_SCALE = 173.7178  # 400 / ln(10)
DEFAULT_INITIAL_RD = 350.0
DEFAULT_INITIAL_VOL = 0.06
GLICKO_FORMULA_C = 3.0  # Constant in g(phi) formula


@dataclass
class GlickoRating:
    """Data class representing a Glicko-2 rating state."""

    rating: float
    rd: float
    vol: float

    def __getitem__(self, key: str) -> float:
        """Allow subscripting for backward compatibility."""
        return getattr(self, key)

    def to_dict(self) -> Dict[str, float]:
        """Convert rating to dictionary format."""
        return asdict(self)

    def copy(self) -> "GlickoRating":
        """Return a copy of the rating."""
        return GlickoRating(self.rating, self.rd, self.vol)


class Glicko2Rating:
    """Team-level Glicko-2 rating system."""

    # Glicko-2 system constants
    TAU = 0.5  # System volatility constant (0.3-1.2, lower = more stable)
    EPSILON = 0.000001
    HOME_ADVANTAGE = 100.0

    def __init__(
        self,
        initial_rating: float = GLICKO_OFFSET,
        initial_rd: float = DEFAULT_INITIAL_RD,
        initial_vol: float = DEFAULT_INITIAL_VOL,
        home_advantage: Optional[float] = None,
    ):
        """
        Initialize Glicko-2 rating system.

        Args:
            initial_rating: Starting rating (1500 is average)
            initial_rd: Starting rating deviation (350 = completely uncertain)
            initial_vol: Starting volatility (0.06 is typical)
            home_advantage: Home advantage in rating points (defaults to class HOME_ADVANTAGE)
        """
        self.ratings = defaultdict(
            lambda: GlickoRating(rating=initial_rating, rd=initial_rd, vol=initial_vol)
        )
        self.home_advantage = (
            home_advantage if home_advantage is not None else self.HOME_ADVANTAGE
        )
        self.initial_rating = initial_rating
        self.initial_rd = initial_rd
        self.initial_vol = initial_vol

    def _get_rating_obj(self, team: str) -> GlickoRating:
        """Get rating as a GlickoRating object, handling legacy dicts."""
        val = self.ratings[team]
        if isinstance(val, dict):
            return GlickoRating(
                rating=val.get("rating", self.initial_rating),
                rd=val.get("rd", self.initial_rd),
                vol=val.get("vol", self.initial_vol),
            )
        return val

    def _scale_down(self, rating: float, rd: float) -> Tuple[float, float]:
        """Convert from Glicko-1 scale to Glicko-2 scale."""
        mu = (rating - GLICKO_OFFSET) / GLICKO_SCALE
        phi = rd / GLICKO_SCALE
        return mu, phi

    def _scale_up(self, mu: float, phi: float) -> Tuple[float, float]:
        """Convert from Glicko-2 scale to Glicko-1 scale."""
        rating = mu * GLICKO_SCALE + GLICKO_OFFSET
        rd = phi * GLICKO_SCALE
        return rating, rd

    def _g(self, phi: float) -> float:
        """Calculate g(φ) function."""
        return 1 / math.sqrt(1 + GLICKO_FORMULA_C * phi**2 / math.pi**2)

    def _e(self, mu: float, mu_j: float, phi_j: float) -> float:
        """Calculate E(μ, μ_j, φ_j) - expected score."""
        return 1 / (1 + math.exp(-self._g(phi_j) * (mu - mu_j)))

    def get_rating(self, team: str) -> Dict[str, float]:
        """Get current Glicko-2 rating for a team."""
        return self._get_rating_obj(team).to_dict()

    def predict(self, home_team: str, away_team: str) -> float:
        """
        Predict probability of home team winning.

        Args:
            home_team: Home team name
            away_team: Away team name

        Returns:
            Probability of home team winning (0.0 to 1.0)
        """
        home = self._get_rating_obj(home_team)
        away = self._get_rating_obj(away_team)

        # Apply home advantage
        home_rating_adj = home.rating + self.home_advantage

        # Scale to Glicko-2
        mu_home, phi_home = self._scale_down(home_rating_adj, home.rd)
        mu_away, phi_away = self._scale_down(away.rating, away.rd)

        # Calculate expected score using Glicko-2 formula
        # Account for both teams' rating deviations
        combined_phi = math.sqrt(phi_home**2 + phi_away**2)

        return self._e(mu_home, mu_away, combined_phi)

    def update(self, home_team: str, away_team: str, home_won: bool) -> Dict:
        """
        Update ratings after a game.

        Args:
            home_team: Home team name
            away_team: Away team name
            home_won: Whether home team won

        Returns:
            Dictionary with rating changes
        """
        # Get current ratings
        home = self.ratings[home_team]
        away = self.ratings[away_team]

        # Apply home advantage for prediction only (not for update)
        home_rating_for_prediction = home.rating + self.home_advantage

        # Update home team
        home_change = self._update_team(
            home,
            away,
            1.0 if home_won else 0.0,
        )

        # Create temporary GlickoRating for away team update because of home advantage
        home_with_adv = GlickoRating(
            rating=home_rating_for_prediction, rd=home.rd, vol=home.vol
        )

        # Update away team
        away_change = self._update_team(
            away,
            home_with_adv,
            1.0 if not home_won else 0.0,
        )

        # Store new ratings
        self.ratings[home_team] = GlickoRating(**home_change["new"])
        self.ratings[away_team] = GlickoRating(**away_change["new"])

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_won": home_won,
            "home_change": home_change,
            "away_change": away_change,
        }

    def _update_team(
        self,
        rating_obj: GlickoRating,
        opp_rating_obj: GlickoRating,
        score: float,
    ) -> Dict:
        """Update a single team's rating using Glicko-2 algorithm."""
        rating = rating_obj.rating
        rd = rating_obj.rd
        vol = rating_obj.vol
        opp_rating = opp_rating_obj.rating
        opp_rd = opp_rating_obj.rd

        # Step 1: Scale down to Glicko-2 scale
        mu, phi = self._scale_down(rating, rd)
        mu_opp, phi_opp = self._scale_down(opp_rating, opp_rd)

        # Step 2: Calculate estimated variance (v)
        g_phi = self._g(phi_opp)
        e_score = self._e(mu, mu_opp, phi_opp)
        v = 1 / (g_phi**2 * e_score * (1 - e_score))

        # Step 3: Calculate improvement (Δ)
        delta = v * g_phi * (score - e_score)

        # Step 4: Update volatility (σ)
        a = math.log(vol**2)

        def f(x):
            ex = math.exp(x)
            num1 = ex * (delta**2 - phi**2 - v - ex)
            den1 = 2 * ((phi**2 + v + ex) ** 2)
            num2 = x - a
            den2 = self.TAU**2
            return num1 / den1 - num2 / den2

        # Solve for new volatility using Illinois algorithm
        A = a
        B = a

        if delta**2 > phi**2 + v:
            B = math.log(delta**2 - phi**2 - v)
        else:
            k = 1
            while f(a - k * self.TAU) < 0:
                k += 1
            B = a - k * self.TAU

        f_A = f(A)
        f_B = f(B)

        # Illinois algorithm iteration
        while abs(B - A) > self.EPSILON:
            C = A + (A - B) * f_A / (f_B - f_A)
            f_C = f(C)

            if f_C * f_B < 0:
                A = B
                f_A = f_B
            else:
                f_A = f_A / 2

            B = C
            f_B = f_C

        new_vol = math.exp(A / 2)

        # Step 5: Update rating deviation
        phi_star = math.sqrt(phi**2 + new_vol**2)

        # Step 6: Update rating and RD
        new_phi = 1 / math.sqrt(1 / phi_star**2 + 1 / v)
        new_mu = mu + new_phi**2 * g_phi * (score - e_score)

        # Step 7: Scale back up
        new_rating, new_rd = self._scale_up(new_mu, new_phi)

        return {
            "old": {"rating": rating, "rd": rd, "vol": vol},
            "new": {"rating": new_rating, "rd": new_rd, "vol": new_vol},
            "delta": new_rating - rating,
            "expected_score": e_score,
            "actual_score": score,
        }

    def decay_rd(self, team: str, periods: int = 1):
        """
        Increase rating deviation for inactive teams.
        Call this during off-season or for teams that haven't played.

        Args:
            team: Team name
            periods: Number of rating periods of inactivity
        """
        team_data = self.ratings[team]
        mu, phi = self._scale_down(team_data.rating, team_data.rd)

        for _ in range(periods):
            phi = math.sqrt(phi**2 + team_data.vol**2)

        _, new_rd = self._scale_up(mu, phi)
        team_data.rd = min(new_rd, self.initial_rd)  # Cap at initial RD


# Sport-specific implementations


class NBAGlicko2Rating(Glicko2Rating):
    """NBA-specific Glicko-2 rating."""

    HOME_ADVANTAGE = 100.0


class NHLGlicko2Rating(Glicko2Rating):
    """NHL-specific Glicko-2 rating."""

    HOME_ADVANTAGE = 50.0


class MLBGlicko2Rating(Glicko2Rating):
    """MLB-specific Glicko-2 rating."""

    HOME_ADVANTAGE = 50.0


class NFLGlicko2Rating(Glicko2Rating):
    """NFL-specific Glicko-2 rating."""

    HOME_ADVANTAGE = 65.0


if __name__ == "__main__":
    print("Testing Glicko-2 Rating System")
    print("=" * 60)

    # Create rating system
    glicko = NBAGlicko2Rating()

    # Simulate some games
    games = [
        ("Lakers", "Celtics", True),
        ("Celtics", "Heat", False),
        ("Lakers", "Heat", True),
        ("Heat", "Lakers", True),
        ("Celtics", "Lakers", True),
    ]

    print("\nSimulating games:\n")

    for home, away, home_won in games:
        # Predict before update
        prob = glicko.predict(home, away)

        # Update ratings
        result = glicko.update(home, away, home_won)

        outcome = "WON" if home_won else "LOST"
        print(f"{home} vs {away}: {home} {outcome} (predicted: {prob:.1%})")
        print(
            f"  {home}: {result['home_change']['old']['rating']:.1f} → "
            f"{result['home_change']['new']['rating']:.1f} "
            f"(±{result['home_change']['new']['rd']:.1f}, "
            f"σ={result['home_change']['new']['vol']:.4f})"
        )
        print(
            f"  {away}: {result['away_change']['old']['rating']:.1f} → "
            f"{result['away_change']['new']['rating']:.1f} "
            f"(±{result['away_change']['new']['rd']:.1f}, "
            f"σ={result['away_change']['new']['vol']:.4f})"
        )
        print()

    print("\nFinal Ratings:")
    print("-" * 60)
    for team in sorted(glicko.ratings.keys()):
        r = glicko.ratings[team]
        print(f"{team:15} {r.rating:7.1f} ± {r.rd:5.1f}  (vol: {r.vol:.4f})")
