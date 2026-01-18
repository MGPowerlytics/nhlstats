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
from typing import Dict, Tuple
from collections import defaultdict


class Glicko2Rating:
    """Team-level Glicko-2 rating system."""
    
    # Glicko-2 system constants
    TAU = 0.5  # System volatility constant (0.3-1.2, lower = more stable)
    EPSILON = 0.000001
    
    def __init__(self, initial_rating: float = 1500, initial_rd: float = 350, 
                 initial_vol: float = 0.06, home_advantage: float = 100):
        """
        Initialize Glicko-2 rating system.
        
        Args:
            initial_rating: Starting rating (1500 is average)
            initial_rd: Starting rating deviation (350 = completely uncertain)
            initial_vol: Starting volatility (0.06 is typical)
            home_advantage: Home advantage in rating points
        """
        self.ratings = defaultdict(lambda: {
            'rating': initial_rating,
            'rd': initial_rd,
            'vol': initial_vol
        })
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.initial_rd = initial_rd
        self.initial_vol = initial_vol
    
    def _scale_down(self, rating: float, rd: float) -> Tuple[float, float]:
        """Convert from Glicko-1 scale to Glicko-2 scale."""
        mu = (rating - 1500) / 173.7178
        phi = rd / 173.7178
        return mu, phi
    
    def _scale_up(self, mu: float, phi: float) -> Tuple[float, float]:
        """Convert from Glicko-2 scale to Glicko-1 scale."""
        rating = mu * 173.7178 + 1500
        rd = phi * 173.7178
        return rating, rd
    
    def _g(self, phi: float) -> float:
        """Calculate g(φ) function."""
        return 1 / math.sqrt(1 + 3 * phi ** 2 / math.pi ** 2)
    
    def _e(self, mu: float, mu_j: float, phi_j: float) -> float:
        """Calculate E(μ, μ_j, φ_j) - expected score."""
        return 1 / (1 + math.exp(-self._g(phi_j) * (mu - mu_j)))
    
    def get_rating(self, team: str) -> Dict:
        """Get current Glicko-2 rating for a team."""
        return self.ratings[team].copy()
    
    def predict(self, home_team: str, away_team: str) -> float:
        """
        Predict probability of home team winning.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            Probability of home team winning (0.0 to 1.0)
        """
        home = self.ratings[home_team]
        away = self.ratings[away_team]
        
        # Apply home advantage
        home_rating_adj = home['rating'] + self.home_advantage
        
        # Scale to Glicko-2
        mu_home, phi_home = self._scale_down(home_rating_adj, home['rd'])
        mu_away, phi_away = self._scale_down(away['rating'], away['rd'])
        
        # Calculate expected score using Glicko-2 formula
        # Account for both teams' rating deviations
        combined_phi = math.sqrt(phi_home ** 2 + phi_away ** 2)
        
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
        home_rating_for_prediction = home['rating'] + self.home_advantage
        
        # Update home team
        home_change = self._update_team(
            home['rating'], home['rd'], home['vol'],
            away['rating'], away['rd'],
            1.0 if home_won else 0.0,
            home_advantage=self.home_advantage
        )
        
        # Update away team  
        away_change = self._update_team(
            away['rating'], away['rd'], away['vol'],
            home_rating_for_prediction, home['rd'],
            1.0 if not home_won else 0.0,
            home_advantage=0  # Away team doesn't get advantage
        )
        
        # Store new ratings
        self.ratings[home_team] = home_change['new']
        self.ratings[away_team] = away_change['new']
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_won': home_won,
            'home_change': home_change,
            'away_change': away_change
        }
    
    def _update_team(self, rating: float, rd: float, vol: float,
                     opp_rating: float, opp_rd: float, score: float,
                     home_advantage: float = 0) -> Dict:
        """Update a single team's rating using Glicko-2 algorithm."""
        
        # Step 1: Scale down to Glicko-2 scale
        mu, phi = self._scale_down(rating, rd)
        mu_opp, phi_opp = self._scale_down(opp_rating, opp_rd)
        
        # Step 2: Calculate estimated variance (v)
        g_phi = self._g(phi_opp)
        e_score = self._e(mu, mu_opp, phi_opp)
        v = 1 / (g_phi ** 2 * e_score * (1 - e_score))
        
        # Step 3: Calculate improvement (Δ)
        delta = v * g_phi * (score - e_score)
        
        # Step 4: Update volatility (σ)
        a = math.log(vol ** 2)
        
        def f(x):
            ex = math.exp(x)
            num1 = ex * (delta ** 2 - phi ** 2 - v - ex)
            den1 = 2 * ((phi ** 2 + v + ex) ** 2)
            num2 = x - a
            den2 = self.TAU ** 2
            return num1 / den1 - num2 / den2
        
        # Solve for new volatility using Illinois algorithm
        A = a
        B = a
        
        if delta ** 2 > phi ** 2 + v:
            B = math.log(delta ** 2 - phi ** 2 - v)
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
        phi_star = math.sqrt(phi ** 2 + new_vol ** 2)
        
        # Step 6: Update rating and RD
        new_phi = 1 / math.sqrt(1 / phi_star ** 2 + 1 / v)
        new_mu = mu + new_phi ** 2 * g_phi * (score - e_score)
        
        # Step 7: Scale back up
        new_rating, new_rd = self._scale_up(new_mu, new_phi)
        
        old_rating = rating
        old_rd = rd
        old_vol = vol
        
        return {
            'old': {
                'rating': old_rating,
                'rd': old_rd,
                'vol': old_vol
            },
            'new': {
                'rating': new_rating,
                'rd': new_rd,
                'vol': new_vol
            },
            'delta': new_rating - old_rating,
            'expected_score': e_score,
            'actual_score': score
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
        mu, phi = self._scale_down(team_data['rating'], team_data['rd'])
        
        for _ in range(periods):
            phi = math.sqrt(phi ** 2 + team_data['vol'] ** 2)
        
        _, new_rd = self._scale_up(mu, phi)
        team_data['rd'] = min(new_rd, self.initial_rd)  # Cap at initial RD


# Sport-specific implementations

class NBAGlicko2Rating(Glicko2Rating):
    """NBA-specific Glicko-2 rating."""
    def __init__(self):
        super().__init__(
            initial_rating=1500,
            initial_rd=350,
            initial_vol=0.06,
            home_advantage=100
        )


class NHLGlicko2Rating(Glicko2Rating):
    """NHL-specific Glicko-2 rating."""
    def __init__(self):
        super().__init__(
            initial_rating=1500,
            initial_rd=350,
            initial_vol=0.06,
            home_advantage=50
        )


class MLBGlicko2Rating(Glicko2Rating):
    """MLB-specific Glicko-2 rating."""
    def __init__(self):
        super().__init__(
            initial_rating=1500,
            initial_rd=350,
            initial_vol=0.06,
            home_advantage=50
        )


class NFLGlicko2Rating(Glicko2Rating):
    """NFL-specific Glicko-2 rating."""
    def __init__(self):
        super().__init__(
            initial_rating=1500,
            initial_rd=350,
            initial_vol=0.06,
            home_advantage=65
        )


if __name__ == '__main__':
    print("Testing Glicko-2 Rating System")
    print("=" * 60)
    
    # Create rating system
    glicko = NBAGlicko2Rating()
    
    # Simulate some games
    games = [
        ('Lakers', 'Celtics', True),
        ('Celtics', 'Heat', False),
        ('Lakers', 'Heat', True),
        ('Heat', 'Lakers', True),
        ('Celtics', 'Lakers', True),
    ]
    
    print("\nSimulating games:\n")
    
    for home, away, home_won in games:
        # Predict before update
        prob = glicko.predict(home, away)
        
        # Update ratings
        result = glicko.update(home, away, home_won)
        
        outcome = "WON" if home_won else "LOST"
        print(f"{home} vs {away}: {home} {outcome} (predicted: {prob:.1%})")
        print(f"  {home}: {result['home_change']['old']['rating']:.1f} → "
              f"{result['home_change']['new']['rating']:.1f} "
              f"(±{result['home_change']['new']['rd']:.1f}, "
              f"σ={result['home_change']['new']['vol']:.4f})")
        print(f"  {away}: {result['away_change']['old']['rating']:.1f} → "
              f"{result['away_change']['new']['rating']:.1f} "
              f"(±{result['away_change']['new']['rd']:.1f}, "
              f"σ={result['away_change']['new']['vol']:.4f})")
        print()
    
    print("\nFinal Ratings:")
    print("-" * 60)
    for team in sorted(glicko.ratings.keys()):
        r = glicko.ratings[team]
        print(f"{team:15} {r['rating']:7.1f} ± {r['rd']:5.1f}  (vol: {r['vol']:.4f})")
