"""Portfolio types for betting system."""

from dataclasses import dataclass
from datetime import date
from typing import Optional, List, Dict, Any
from enum import Enum


class BetSide(Enum):
    YES = "yes"
    NO = "no"


@dataclass
class BetOpportunity:
    """Represents a betting opportunity."""
    sport: str
    ticker: str
    side: BetSide
    edge: float
    confidence: float
    kelly_fraction: float
    amount: float
    market_id: Optional[str] = None
    event_ticker: Optional[str] = None
    event_name: Optional[str] = None
    event_date: Optional[date] = None
    settle_date: Optional[date] = None
    max_bet_size: Optional[float] = None
    min_bet_size: Optional[float] = None
    current_price: Optional[float] = None
    fair_price: Optional[float] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'sport': self.sport,
            'ticker': self.ticker,
            'side': self.side.value,
            'edge': self.edge,
            'confidence': self.confidence,
            'kelly_fraction': self.kelly_fraction,
            'amount': self.amount,
            'market_id': self.market_id,
            'event_ticker': self.event_ticker,
            'event_name': self.event_name,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'settle_date': self.settle_date.isoformat() if self.settle_date else None,
            'max_bet_size': self.max_bet_size,
            'min_bet_size': self.min_bet_size,
            'current_price': self.current_price,
            'fair_price': self.fair_price,
            'notes': self.notes
        }


def extract_ticker_date(ticker: str) -> Optional[date]:
    """Extract date from ticker string like 'MLB-ATL-WIN-2026-04-12'."""
    try:
        # Look for date pattern in ticker
        import re
        match = re.search(r'(\d{4}-\d{2}-\d{2})', ticker)
        if match:
            from datetime import datetime
            return datetime.strptime(match.group(1), '%Y-%m-%d').date()
    except:
        pass
    return None
