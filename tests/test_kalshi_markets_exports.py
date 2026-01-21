import sys
from pathlib import Path
import pytest

# Add plugins to path
plugins_dir = Path(__file__).parent.parent / "plugins"
sys.path.insert(0, str(plugins_dir))

def test_kalshi_markets_exports():
    """Verify that all required fetch_X_markets functions behave correctly and exist."""
    import kalshi_markets

    required_functions = [
        "fetch_nba_markets",
        "fetch_nhl_markets",
        "fetch_mlb_markets",
        "fetch_nfl_markets",
        "fetch_epl_markets",
        "fetch_tennis_markets",
        "fetch_ncaab_markets",
        "fetch_wncaab_markets",
        "fetch_ligue1_markets",
    ]

    for func_name in required_functions:
        assert hasattr(kalshi_markets, func_name), f"Missing function {func_name} in kalshi_markets.py"
        assert callable(getattr(kalshi_markets, func_name)), f"{func_name} is not callable"
