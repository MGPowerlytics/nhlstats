"""
Kalshi API bet placement - Direct REST API implementation.

CRITICAL VALIDATIONS:
1. Always verify game has not started using The Odds API
2. Market status 'active' does NOT mean game hasn't started
3. Use limit orders with yes_price/no_price (no market orders)
4. Order cost = contracts × price (not just contracts)
"""

import logging
import uuid
import base64
import requests
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from constants import DEFAULT_KALSHI_BET_SIZE
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)


@dataclass
class KalshiConfig:
    """Configuration for Kalshi API client."""

    api_key_id: str
    private_key_path: str
    max_bet_size: float = DEFAULT_KALSHI_BET_SIZE
    production: bool = True
    odds_api_key: Optional[str] = None
    dedupe_dir: Optional[str] = None

    @classmethod
    def from_kalshkey(
        cls,
        key_file: Optional[Union[str, Path]] = None,
        max_bet_size: float = DEFAULT_KALSHI_BET_SIZE,
        production: bool = True,
    ) -> "KalshiConfig":
        """Load and parse Kalshi credentials from kalshkey file.

        Searches in standard locations if key_file is not provided.
        Standard locations:
        - /opt/airflow/kalshkey (for Airflow)
        - kalshkey (local directory)

        Returns:
            KalshiConfig: Valid configuration object
        """
        path = cls._find_kalshkey_file(key_file)
        content = path.read_text(encoding="utf-8")

        api_key_id = cls._extract_api_key_id(content, path)
        private_key_lines = cls._extract_private_key(content, path)

        # Save private key to temp file (to be used by KalshiConfig)
        temp_key_file = Path("/tmp/kalshi_private_key.pem")
        temp_key_file.write_text("\n".join(private_key_lines), encoding="utf-8")

        return cls(
            api_key_id=api_key_id,
            private_key_path=str(temp_key_file),
            max_bet_size=max_bet_size,
            production=production,
        )

    @staticmethod
    def _find_kalshkey_file(key_file: Optional[Union[str, Path]]) -> Path:
        """Find the kalshkey file in standard locations."""
        if key_file:
            path = Path(key_file)
            if path.exists():
                return path

        # Try standard locations
        locations = [Path("/opt/airflow/kalshkey"), Path("kalshkey")]
        for loc in locations:
            if loc.exists():
                return loc

        # If still not found, try searching relative to this file
        path_rel = Path(__file__).resolve().parents[1] / "kalshkey"
        if path_rel.exists():
            return path_rel

        raise FileNotFoundError(
            f"Kalshi credentials file not found (searched: {key_file or 'standard locations'})"
        )

    @staticmethod
    def _extract_api_key_id(content: str, path: Path) -> str:
        """Extract API key ID from kalshkey content."""
        for line in content.splitlines():
            if "API key id:" in line:
                return line.split(":", 1)[1].strip()

        raise ValueError(f"Could not find API key ID in {path}")

    @staticmethod
    def _extract_private_key(content: str, path: Path) -> List[str]:
        """Extract RSA private key from kalshkey content."""
        private_key_lines = []
        in_key = False
        for line in content.splitlines():
            if "-----BEGIN RSA PRIVATE KEY-----" in line:
                in_key = True
            if in_key:
                private_key_lines.append(line)
            if "-----END RSA PRIVATE KEY-----" in line:
                break

        if not private_key_lines:
            raise ValueError(f"Could not extract RSA private key from {path}")

        return private_key_lines


@dataclass
class BettingConfig:
    """Configuration for processing bet recommendations."""

    def __init__(
        self,
        min_confidence: float = 0.75,
        min_edge: float = 0.05,
        dry_run: bool = False,
        trade_date: Optional[str] = None,
        sport_filter: Optional[List[str]] = None,
    ):
        self.min_confidence = min_confidence
        self.min_edge = min_edge
        self.dry_run = dry_run
        self.trade_date = trade_date
        self.sport_filter = sport_filter


@dataclass
class BetContext:
    """Context for processing a single bet recommendation."""

    rec: Dict[str, Any]
    ticker: str
    side: str
    bet_size: float
    elo_prob: float
    edge: float
    match_info: str
    bet_player: str
    dry_run: bool
    trade_date: str
    balance: float

    def process(
        self, client: "KalshiBetting"
    ) -> Tuple[Optional[Dict], Optional[str], float]:
        """Process a single bet (actual or dry run) using the provided client."""
        print(
            f"🎯 {self.match_info}\n   Bet: {self.bet_player}, Side: {self.side.upper()}, "
            f"Size: ${self.bet_size:.2f}, Confidence: {self.elo_prob:.1%}, Edge: {self.edge:.1%}"
        )

        if not self.dry_run:
            market = MarketSide(self.ticker, self.side, self.trade_date)
            result = client.place_bet(market, self.bet_size)
            if result:
                return (
                    {
                        "rec": self.rec,
                        "bet_size": self.bet_size,
                        "side": self.side,
                        "result": result,
                    },
                    None,
                    self.balance - self.bet_size,
                )
            return None, f"Failed: {self.ticker}", self.balance

        print("   [DRY RUN] Would place bet")
        return (
            {
                "rec": self.rec,
                "bet_size": self.bet_size,
                "side": self.side,
                "dry_run": True,
            },
            None,
            self.balance - self.bet_size,
        )


@dataclass
class MarketSide:
    """Represents a specific side of a Kalshi market."""

    ticker: str
    side: str
    trade_date: str


@dataclass
class GameIdentity:
    """Identity of a game for verification."""

    home_team: str
    away_team: str
    sport: str


class SimpleOrderLock:
    """Simple file-based lock to prevent duplicate orders."""

    def __init__(self, lock_dir: Path):
        self.lock_dir = lock_dir
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def reserve(self, market: MarketSide):
        """Reserve a market side to prevent duplicate bets."""
        lock_file = (
            self.lock_dir / f"{market.trade_date}_{market.ticker}_{market.side}.lock"
        )

        # Define Reservation class once
        class Reservation:
            def __init__(self, reserved: bool, reason: str, lock_path: Path):
                self.reserved = reserved
                self.reason = reason
                self.lock_path = lock_path

        if lock_file.exists():
            # Return a reservation object with reserved=False
            return Reservation(
                reserved=False, reason="already locked", lock_path=lock_file
            )
        else:
            lock_file.touch()
            return Reservation(reserved=True, reason="ok", lock_path=lock_file)


class KalshiBetting:
    # Constants for magic numbers
    MIN_BET_SIZE = 0.01
    MAX_POSITION_PCT = 0.05
    DEFAULT_TIMEOUT = 30
    DEFAULT_BALANCE = 100.0
    MS_PER_SECOND = 1000
    ODDS_API_TIMEOUT = 5
    HTTP_OK = 200
    KELLY_DIVISOR = 4.0
    CENTS_PER_DOLLAR = 100

    # Map sport to Odds API sport key
    SPORT_TO_ODDS_API = {
        "NBA": "basketball_nba",
        "NHL": "icehockey_nhl",
        "MLB": "baseball_mlb",
        "NFL": "americanfootball_nfl",
        "NCAAB": "basketball_ncaab",
        "EPL": "soccer_epl",
        "LIGUE1": "soccer_france_ligue_1",
    }

    def __init__(
        self,
        *args,
        config: Optional[KalshiConfig] = None,
        **kwargs,
    ):
        """
        Initialize Kalshi betting client.

        Preferred usage: KalshiBetting(config=KalshiConfig(...))

        Legacy usage (deprecated): KalshiBetting(api_key_id="...", private_key_path="...", ...)
        """
        config = self._parse_constructor_args(args, config, kwargs)
        config = self._ensure_api_key_id(config)

        self.config = config
        self.base_url = (
            "https://api.elections.kalshi.com"
            if config.production
            else "https://demo-api.kalshi.co"
        )
        self._deduper = SimpleOrderLock(Path(config.dedupe_dir or "data/order_dedup"))

        # Load private key - be robust about format and location
        print("🔐 Loading private key...")
        self.private_key = self._load_private_key(config.private_key_path)
        print(f"✅ Connected to {self.base_url}")

        # Cache for The Odds API scores to avoid repeated calls
        self._scores_cache = {}
        self._scores_cache_time = {}
        self.CACHE_DURATION = 300  # 5 minutes

    def _parse_constructor_args(
        self,
        args: tuple,
        config: Optional[KalshiConfig],
        kwargs: dict,
    ) -> KalshiConfig:
        """
        Parse constructor arguments to create a KalshiConfig.

        Handles multiple initialization patterns:
        1. KalshiBetting(config=KalshiConfig(...)) - preferred
        2. KalshiBetting(KalshiConfig(...)) - positional config
        3. Legacy keyword arguments (deprecated)
        4. Legacy positional arguments (deprecated)

        Returns:
            KalshiConfig: Valid configuration object
        """
        # Handle positional arguments
        if args:
            return self._parse_positional_args(args, kwargs)

        # Handle legacy keyword arguments (without config)
        if not config and kwargs:
            return self._parse_legacy_keyword_args(kwargs)

        # Create default config if none provided
        if not config:
            return KalshiConfig(api_key_id="", private_key_path="")

        return config

    def _parse_positional_args(self, args: tuple, kwargs: dict) -> KalshiConfig:
        """Parse positional arguments to create KalshiConfig."""
        if len(args) == 1 and isinstance(args[0], KalshiConfig):
            # Single positional KalshiConfig
            return args[0]

        # Legacy positional arguments: api_key_id, private_key_path, max_bet_size, production
        import warnings

        warnings.warn(
            "Positional arguments for KalshiBetting are deprecated. "
            "Use KalshiBetting(config=KalshiConfig(...)) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        api_key_id = args[0] if len(args) > 0 else None
        private_key_path = args[1] if len(args) > 1 else None
        max_bet_size = args[2] if len(args) > 2 else DEFAULT_KALSHI_BET_SIZE
        production = args[3] if len(args) > 3 else True

        # Merge with keyword arguments
        api_key_id = kwargs.pop("api_key_id", api_key_id)
        private_key_path = kwargs.pop("private_key_path", private_key_path)
        max_bet_size = kwargs.pop("max_bet_size", max_bet_size)
        production = kwargs.pop("production", production)
        odds_api_key = kwargs.pop("odds_api_key", None)
        dedupe_dir = kwargs.pop("dedupe_dir", None)

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")

        return KalshiConfig(
            api_key_id=api_key_id or "",
            private_key_path=private_key_path or "",
            max_bet_size=max_bet_size,
            production=production,
            odds_api_key=odds_api_key,
            dedupe_dir=dedupe_dir,
        )

    def _parse_legacy_keyword_args(self, kwargs: dict) -> KalshiConfig:
        """Parse legacy keyword arguments to create KalshiConfig."""
        import warnings

        warnings.warn(
            "Keyword arguments for KalshiBetting are deprecated. "
            "Use KalshiBetting(config=KalshiConfig(...)) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        api_key_id = kwargs.pop("api_key_id", None)
        private_key_path = kwargs.pop("private_key_path", None)
        max_bet_size = kwargs.pop("max_bet_size", DEFAULT_KALSHI_BET_SIZE)
        production = kwargs.pop("production", True)
        odds_api_key = kwargs.pop("odds_api_key", None)
        dedupe_dir = kwargs.pop("dedupe_dir", None)

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")

        return KalshiConfig(
            api_key_id=api_key_id or "",
            private_key_path=private_key_path or "",
            max_bet_size=max_bet_size,
            production=production,
            odds_api_key=odds_api_key,
            dedupe_dir=dedupe_dir,
        )

    def _ensure_api_key_id(self, config: KalshiConfig) -> KalshiConfig:
        """
        Ensure API key ID is loaded, auto-loading from credentials if missing.

        Args:
            config: KalshiConfig object

        Returns:
            KalshiConfig with API key ID populated if possible
        """
        if not config.api_key_id:
            try:
                from kalshi_markets import load_kalshi_credentials

                loaded_id, _ = load_kalshi_credentials()
                config.api_key_id = loaded_id
            except Exception as e:
                print(f"   ⚠️  Could not auto-load API Key ID: {e}")

        return config

    @property
    def api_key_id(self) -> str:
        return self.config.api_key_id

    @property
    def max_bet_size(self) -> float:
        return self.config.max_bet_size

    @property
    def odds_api_key(self) -> Optional[str]:
        return self.config.odds_api_key

    @property
    def production(self) -> bool:
        return self.config.production

    @property
    def dedupe_dir(self) -> Optional[str]:
        return self.config.dedupe_dir

    @property
    def private_key_path(self) -> str:
        return self.config.private_key_path

    @property
    def min_bet_size(self) -> float:
        return self.MIN_BET_SIZE

    @property
    def max_position_pct(self) -> float:
        return self.MAX_POSITION_PCT

    def _load_private_key(self, path: str):
        """Robustly load the private key from path or environment."""
        try:
            # First attempt: directly load from path if it's a file
            if Path(path).is_file():
                with open(path, "rb") as f:
                    return serialization.load_pem_private_key(
                        f.read(), password=None, backend=default_backend()
                    )

            # Fallback: try to use the credential loader from kalshi_markets
            from kalshi_markets import load_kalshi_credentials

            _, priv_key_str = load_kalshi_credentials()
            return serialization.load_pem_private_key(
                priv_key_str.encode("utf-8")
                if isinstance(priv_key_str, str)
                else priv_key_str,
                password=None,
                backend=default_backend(),
            )
        except Exception as e:
            print(f"   ⚠️  Failed to load private key: {e}")
            raise e

    def _create_signature(self, timestamp: str, method: str, path: str) -> str:
        """Create HMAC-SHA256 signature for Kalshi API."""
        path_without_query = path.split("?")[0]
        message = f"{timestamp}{method}{path_without_query}".encode("utf-8")
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate request headers with authentication."""
        timestamp = str(int(datetime.now().timestamp() * self.MS_PER_SECOND))
        return {
            "KALSHI-ACCESS-KEY": self.config.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": self._create_signature(timestamp, method, path),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        """Unified request handler for GET and POST."""
        url = self.base_url + path
        headers = self._get_headers(method, path)

        try:
            if method == "GET":
                response = requests.get(
                    url, headers=headers, timeout=self.DEFAULT_TIMEOUT
                )
            else:
                response = requests.post(
                    url, headers=headers, json=data, timeout=self.DEFAULT_TIMEOUT
                )

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            print(f"HTTP {response.status_code} error for {path}: {response.text}")
            raise

    def _get(self, path: str) -> Dict:
        return self._request("GET", path)

    def _post(self, path: str, data: Dict) -> Dict:
        return self._request("POST", path, data)

    def get_balance(self) -> Tuple[float, float]:
        try:
            response = self._get("/trade-api/v2/portfolio/balance")
            return (
                response.get("balance", 0) / self.CENTS_PER_DOLLAR,
                response.get("portfolio_value", response.get("balance", 0))
                / self.CENTS_PER_DOLLAR,
            )
        except requests.exceptions.HTTPError as e:
            print(f"⚠️  Failed to get balance: {e}")
            if e.response:
                print(f"  Response body: {e.response.text}")
            return self.DEFAULT_BALANCE, self.DEFAULT_BALANCE
        except Exception as e:
            print(f"⚠️  Failed to get balance: {e}")
            return self.DEFAULT_BALANCE, self.DEFAULT_BALANCE

    def get_market_details(self, ticker: str) -> Optional[Dict]:
        """Get market details from Kalshi API.

        Args:
            ticker: Market ticker (e.g., 'KXNBAGAME-26JAN20LAL-LAL')

        Returns:
            Market details dict or None if error/invalid ticker
        """
        # Validate ticker
        if not ticker or ticker is None:
            return None

        try:
            return self._get(f"/trade-api/v2/markets/{ticker}").get("market")
        except Exception as e:
            print(f"⚠️  Failed to get market {ticker}: {e}")
            return None

    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name for comparison (lowercase, alphanumeric)."""
        import re

        return re.sub(r"[^a-z0-9]", "", name.lower())

    def _get_scores_cached(self, sport_key: str) -> List[Dict]:
        """Fetch scores from The Odds API with caching."""
        now = time.time()
        cached_time = self._scores_cache_time.get(sport_key, 0)

        if now - cached_time < self.CACHE_DURATION:
            return self._scores_cache.get(sport_key, [])

        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/"
            params = {"apiKey": self.config.odds_api_key, "daysFrom": 1}
            response = requests.get(url, params=params, timeout=self.ODDS_API_TIMEOUT)

            if response.status_code == self.HTTP_OK:
                scores = response.json()
                self._scores_cache[sport_key] = scores
                self._scores_cache_time[sport_key] = now
                return scores
            return []
        except Exception as e:
            print(f"   ⚠️  Error fetching scores for {sport_key}: {e}")
            return []

    def verify_game_not_started(self, game: GameIdentity) -> bool:
        """
        Verify game has not started using The Odds API.
        Returns True if game has NOT started, False if it has.
        """
        if not self.config.odds_api_key:
            print("   ⚠️  No Odds API key - cannot verify game start time")
            return True

        sport_key = self.SPORT_TO_ODDS_API.get(game.sport.upper())
        if not sport_key:
            return True

        scores = self._get_scores_cached(sport_key)
        home_norm = self._normalize_team_name(game.home_team)
        away_norm = self._normalize_team_name(game.away_team)

        for s_game in scores:
            game_home = self._normalize_team_name(s_game.get("home_team", ""))
            game_away = self._normalize_team_name(s_game.get("away_team", ""))

            # Match teams (bidirectional contains check)
            if (home_norm in game_home or game_home in home_norm) and (
                away_norm in game_away or game_away in away_norm
            ):
                if s_game.get("scores") or s_game.get("completed"):
                    print(
                        f"   ❌ Game has STARTED/COMPLETED: {s_game.get('commence_time')}"
                    )
                    return False

        return True

    def is_game_started(self, market: Dict) -> bool:
        """Legacy check - only checks Kalshi market status."""
        if market.get("status", "").lower() in ["closed", "settled", "finalized"]:
            return True
        close_time = market.get("close_time")
        if not close_time:
            return False
        try:
            return datetime.now(timezone.utc) >= datetime.fromisoformat(
                close_time.replace("Z", "+00:00")
            )
        except Exception:
            return False

    def calculate_bet_size(self, rec: Dict[str, Any], balance: float) -> float:
        """
        Calculate optimal bet size using Kelly Criterion.
        Prioritizes pre-calculated kelly_fraction from recommendation.
        """
        # 1. Try to use pre-calculated kelly_fraction
        kelly_fraction = rec.get("kelly_fraction")

        # 2. If not available, use crude approximation (backward compatibility)
        if kelly_fraction is None:
            edge = rec.get("edge", 0)
            kelly_fraction = edge / self.KELLY_DIVISOR

        # 3. Apply sizing constraints
        bet_size = balance * kelly_fraction

        return round(
            max(
                self.MIN_BET_SIZE,
                min(
                    self.config.max_bet_size, balance * self.MAX_POSITION_PCT, bet_size
                ),
            ),
            2,
        )

    def _fetch_from_kalshi_api(
        self, endpoint: str, data_key: str, error_message: str
    ) -> List[Dict]:
        """Fetch data from Kalshi API with error handling.

        Args:
            endpoint: API endpoint to call
            data_key: Key in response JSON containing the data
            error_message: Error message prefix for logging

        Returns:
            List of data items or empty list on error
        """
        try:
            response = self._get(endpoint)
            return response.get(data_key, [])
        except Exception as e:
            print(f"⚠️  {error_message}: {e}")
            return []

    def get_open_positions(self) -> List[Dict]:
        """Fetch all open positions from Kalshi API."""
        return self._fetch_from_kalshi_api(
            endpoint="/trade-api/v2/portfolio/positions",
            data_key="positions",
            error_message="Failed to get open positions",
        )

    def get_open_orders(self) -> List[Dict]:
        """Fetch all resting orders from Kalshi API."""
        return self._fetch_from_kalshi_api(
            endpoint="/trade-api/v2/portfolio/orders?status=resting",
            data_key="orders",
            error_message="Failed to get open orders",
        )

    def get_match_prefix(self, ticker: str) -> str:
        """Extract match/event prefix from ticker."""
        parts = ticker.split("-")
        return "-".join(parts[:-1]) if len(parts) >= 2 else ticker

    def place_bet(
        self,
        market: MarketSide,
        amount: float,
        price: Optional[int] = None,
    ) -> Optional[Dict]:
        """
        Place a limit order on Kalshi with match-level locking.
        """
        # 1. Acquire market lock and validate
        reservation = self._acquire_market_lock(market)
        if reservation is None:
            return None

        # 2. Check for existing positions on this match
        if self._has_existing_position(market):
            self._release_lock(reservation)
            return None

        # 3. Get market price if not provided
        resolved_price = self._get_market_price(market, price)
        if resolved_price is None:
            self._release_lock(reservation)
            return None

        # 4. Calculate number of contracts
        contracts = self._calculate_contracts(amount, resolved_price)
        if contracts < 1:
            self._release_lock(reservation)
            return None

        # 5. Place the order
        return self._place_order(market, contracts, resolved_price)

    def _acquire_market_lock(self, market: MarketSide) -> Optional[Any]:
        """Acquire local filesystem lock for the market."""
        if not market.ticker:
            return None

        reservation = self._deduper.reserve(market)
        if not reservation.reserved:
            logger.warning("Skipping: %s locally locked", market.ticker)
            return None
        return reservation

    def _has_existing_position(self, market: MarketSide) -> bool:
        """Check if we already have an open position OR resting order on this match.

        Checks three sources in order:
          1. DB placed_bets — survives container restarts (H1 fix)
          2. Kalshi open positions API
          3. Kalshi resting orders API
        """
        match_prefix = self.get_match_prefix(market.ticker)

        # 1. DB check — primary dedup guard (survives container restarts)
        try:
            from db_manager import default_db

            result = default_db.execute(
                """
                SELECT COUNT(*) FROM placed_bets
                WHERE ticker LIKE :prefix
                  AND status = 'open'
                  AND placed_date >= CURRENT_DATE
                """,
                {"prefix": f"{match_prefix}%"},
            )
            row = result.fetchone()
            if row and row[0] > 0:
                logger.info("Skipping %s: open position already in DB", match_prefix)
                return True
        except Exception as exc:
            logger.warning("DB dedup check failed for %s: %s", match_prefix, exc)

        # 2. Check open positions from Kalshi API
        open_positions = self.get_open_positions()
        for pos in open_positions:
            if self.get_match_prefix(pos.get("ticker", "")) == match_prefix:
                logger.info("Skipping: Already have open position on %s", match_prefix)
                return True

        # 3. Check resting orders from Kalshi API
        resting_orders = self.get_open_orders()
        for order in resting_orders:
            if self.get_match_prefix(order.get("ticker", "")) == match_prefix:
                logger.info("Skipping: Already have resting order on %s", match_prefix)
                return True

        return False

    def _release_lock(self, reservation: Any) -> None:
        """Release the local filesystem lock."""
        try:
            reservation.lock_path.unlink()
        except Exception:
            pass

    def _get_market_price(
        self, market: MarketSide, price: Optional[int]
    ) -> Optional[int]:
        """Get current market price if not provided."""
        if price is not None:
            return price

        details = self.get_market_details(market.ticker)
        if not details:
            return None

        resolved_price = details.get(f"{market.side}_ask")
        if not resolved_price:
            return None

        return resolved_price

    def _calculate_contracts(self, amount: float, price: int) -> int:
        """Calculate number of contracts based on amount and price."""
        return int((amount * self.CENTS_PER_DOLLAR) / price)

    def _place_order(
        self, market: MarketSide, contracts: int, price: int
    ) -> Optional[Dict]:
        """Place the actual order with Kalshi API."""
        order_data = {
            "ticker": market.ticker,
            "action": "buy",
            "side": market.side,
            "count": contracts,
            "type": "limit",
            f"{market.side}_price": price,
            "client_order_id": str(uuid.uuid4()),
        }

        try:
            response = self._post("/trade-api/v2/portfolio/orders", order_data)
            print(
                f"   ✅ Order placed: {market.ticker} {market.side.upper()} {contracts} @ {price}¢"
            )
            return response
        except Exception as e:
            print(f"   ❌ Order failed: {e}")
            return None

    def _should_process_recommendation(
        self,
        rec: Dict,
        config: BettingConfig,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a recommendation should be processed."""
        if config.sport_filter and rec.get("sport", "").upper() not in [
            s.upper() for s in config.sport_filter
        ]:
            return False, "Sport filter"

        if rec.get("elo_prob", 0) < config.min_confidence:
            return False, "Low confidence"

        if rec.get("edge", 0) < config.min_edge:
            return False, "Low edge"

        return True, None

    def _validate_recommendation(
        self,
        rec: Dict,
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Validate recommendation and get market details."""
        ticker = rec.get("ticker")
        if not ticker:
            return False, "No ticker", None

        market = self.get_market_details(ticker)
        if not market:
            return False, f"Market not found: {ticker}", None

        return True, None, market

    def _check_game_started(
        self,
        rec: Dict,
        market: Dict,
    ) -> Tuple[bool, Optional[str]]:
        """Check if game has started or market is closed."""
        sport = rec.get("sport", "NBA")

        if sport.lower() != "tennis":
            game = GameIdentity(rec["home_team"], rec["away_team"], sport)
            if not self.verify_game_not_started(game):
                return True, "Game already started"

        if self.is_game_started(market):
            return True, "Market closed"

        return False, None

    def _determine_bet_side(
        self,
        rec: Dict,
        sport: str,
        ticker: str,
        market: Dict,
    ) -> str:
        """Determine bet side (YES or NO)."""
        if sport.lower() == "tennis":
            ticker_parts = ticker.split("-")
            if len(ticker_parts) >= 3:
                yes_abbr = ticker_parts[-1].upper()
                bet_on = rec["bet_on"].upper()
                return (
                    "yes"
                    if any(w[:3].upper() == yes_abbr[:3] for w in bet_on.split())
                    else "no"
                )
            return "yes" if rec["bet_on"] in market.get("title", "") else "no"
        return "yes" if rec["bet_on"] == "home" else "no"

    def _format_match_info(self, rec: Dict, sport: str) -> Tuple[str, str]:
        """Format match info for display."""
        if sport.lower() == "tennis":
            return rec.get("matchup", "Unknown match"), rec["bet_on"]
        return f"{rec['away_team']} @ {rec['home_team']}", rec["bet_on"]

    def _process_single_bet(
        self,
        ctx: BetContext,
    ) -> Tuple[Optional[Dict], Optional[str], float]:
        """Process a single bet (actual or dry run). Delegate to context."""
        return ctx.process(self)

    def process_bet_recommendations(
        self,
        recommendations: List[Dict],
        *args,
        config: Optional[BettingConfig] = None,
        **kwargs,
    ) -> Dict:
        """Process bet recommendations using provided configuration.

        Preferred usage: process_bet_recommendations(recommendations, config=BettingConfig(...))

        Legacy usage (deprecated): process_bet_recommendations(recommendations, min_confidence=0.75, ...)
        """
        # Handle legacy keyword arguments
        if not config and kwargs:
            import warnings

            warnings.warn(
                "Keyword arguments for process_bet_recommendations are deprecated. "
                "Use config=BettingConfig(...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            min_confidence = kwargs.pop("min_confidence", 0.75)
            min_edge = kwargs.pop("min_edge", 0.05)
            dry_run = kwargs.pop("dry_run", False)
            trade_date = kwargs.pop("trade_date", None)
            sport_filter = kwargs.pop("sport_filter", None)

            if kwargs:
                raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")

            config = BettingConfig(
                min_confidence=min_confidence,
                min_edge=min_edge,
                dry_run=dry_run,
                trade_date=trade_date,
                sport_filter=sport_filter,
            )

        # Create default config if none provided
        if not config:
            config = BettingConfig()

        trade_date = config.trade_date or datetime.now(timezone.utc).strftime(
            "%Y-%m-%d"
        )

        balance, portfolio_value = self.get_balance()
        print(
            f"\n💰 Starting balance: ${balance:.2f}\n📊 Portfolio value: ${portfolio_value:.2f}\n"
        )

        placed, skipped, errors = [], [], []

        for rec in recommendations:
            res, skip, err, balance = self._process_recommendation_item(
                rec, config, balance, trade_date
            )
            if res:
                placed.append(res)
            if skip:
                skipped.append({"rec": rec, "reason": skip})
            if err:
                errors.append(err)
            time.sleep(1)

        return {
            "placed": placed,
            "skipped": skipped,
            "errors": errors,
            "balance": balance,
        }

    def _process_recommendation_item(
        self,
        rec: Dict[str, Any],
        config: BettingConfig,
        balance: float,
        trade_date: str,
    ) -> Tuple[Optional[Dict], Optional[str], Optional[str], float]:
        """Process a single recommendation item."""
        should_process, skip_reason = self._should_process_recommendation(rec, config)
        if not should_process:
            return None, skip_reason, None, balance

        is_valid, error_msg, market_details = self._validate_recommendation(rec)
        if not is_valid:
            return None, None, error_msg, balance

        # market_details is guaranteed to be non-None after validation
        assert market_details is not None, (
            "market_details should not be None after validation"
        )

        should_skip, skip_reason = self._check_game_started(rec, market_details)
        if should_skip:
            return None, skip_reason, None, balance

        bet_size = self.calculate_bet_size(rec, balance)
        if bet_size < self.MIN_BET_SIZE:
            return None, "Insufficient balance", None, balance

        sport = rec.get("sport", "NBA")
        ticker = rec.get("ticker", "")
        side = self._determine_bet_side(rec, sport, ticker, market_details)
        match_info, bet_player = self._format_match_info(rec, sport)

        ctx = BetContext(
            rec,
            ticker,
            side,
            bet_size,
            rec.get("elo_prob", 0),
            rec.get("edge", 0),
            match_info,
            bet_player,
            config.dry_run,
            trade_date,
            balance,
        )

        res, err, balance = self._process_single_bet(ctx)
        return res, None, err, balance


if __name__ == "__main__":
    with open("kalshkey", "r") as f:
        api_key_id = f.readline().strip().split(": ")[-1]
    print(f"Testing... API Key: {api_key_id[:30]}...\n")
    try:
        config = KalshiConfig(
            api_key_id=api_key_id,
            private_key_path="kalshi_private_key.pem",
            max_bet_size=DEFAULT_KALSHI_BET_SIZE,
            production=True,
        )
        client = KalshiBetting(config=config)
        balance, portfolio = client.get_balance()
        print(f"\n✅ Balance: ${balance:.2f}\n✅ Portfolio: ${portfolio:.2f}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
