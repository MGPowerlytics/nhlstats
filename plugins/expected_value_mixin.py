"""Mixin class for expected_value property to eliminate code duplication.

This addresses the HIGH priority duplicate code smell identified in the
code smell report where identical expected_value property definitions
appeared in both BettingOutcome and BetOpportunity classes.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # For type checking only - avoids circular imports
    from plugins.utils import expected_value
else:
    from plugins.utils import expected_value


class ExpectedValueMixin:
    """Mixin that provides an expected_value property.

    This eliminates duplicate code by providing a single implementation
    of the expected_value property that can be used by multiple classes.

    Classes using this mixin must have 'edge' and 'market_prob' attributes.
    """

    # Type hints for attributes that must be provided by subclasses
    edge: float
    market_prob: float

    @property
    def expected_value(self) -> float:
        """Calculate expected value as percentage of stake.

        Expected Value = edge / market_prob, where:
        - edge = elo_prob - market_prob (our probability advantage)
        - market_prob = market-implied probability (1 / decimal_odds)

        Returns:
            Expected value as a decimal (e.g., 0.05 for 5% expected return)
        """
        return expected_value(self.edge, self.market_prob)
