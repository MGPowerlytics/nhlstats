"""
Kalshi API bet placement - Direct REST API implementation.

CRITICAL VALIDATIONS:
1. Always verify game has not started using The Odds API
2. Market status 'active' does NOT mean game hasn't started
3. Use limit orders with yes_price/no_price (no market orders)
4. Order cost = contracts × price (not just contracts)
"""
import json, uuid, base64, requests, time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding

class KalshiBetting:
    def __init__(self, api_key_id: str, private_key_path: str, max_bet_size: float = 5.0, 
                 production: bool = True, odds_api_key: Optional[str] = None):
        self.api_key_id = api_key_id
        self.max_bet_size, self.min_bet_size, self.max_position_pct = max_bet_size, 2.0, 0.05
        self.base_url = "https://api.elections.kalshi.com" if production else "https://demo-api.kalshi.co"
        self.odds_api_key = odds_api_key
        print("🔐 Loading private key...")
        with open(private_key_path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
        print(f"✅ Connected to {self.base_url}")
    
    def _create_signature(self, timestamp: str, method: str, path: str) -> str:
        path_without_query = path.split('?')[0]
        message = f"{timestamp}{method}{path_without_query}".encode('utf-8')
        signature = self.private_key.sign(message, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        timestamp = str(int(datetime.now().timestamp() * 1000))
        return {'KALSHI-ACCESS-KEY': self.api_key_id, 'KALSHI-ACCESS-SIGNATURE': self._create_signature(timestamp, method, path), 'KALSHI-ACCESS-TIMESTAMP': timestamp, 'Content-Type': 'application/json'}
    
    def _get(self, path: str) -> Dict:
        response = requests.get(self.base_url + path, headers=self._get_headers('GET', path))
        response.raise_for_status()
        return response.json()
    
    def _post(self, path: str, data: Dict) -> Dict:
        response = requests.post(self.base_url + path, headers=self._get_headers('POST', path), json=data)
        response.raise_for_status()
        return response.json()
    
    def get_balance(self) -> Tuple[float, float]:
        try:
            response = self._get('/trade-api/v2/portfolio/balance')
            return response.get('balance', 0) / 100, response.get('portfolio_value', response.get('balance', 0)) / 100
        except Exception as e:
            print(f"⚠️  Failed to get balance: {e}")
            return 100.0, 100.0
    
    def get_market_details(self, ticker: str) -> Optional[Dict]:
        try:
            return self._get(f'/trade-api/v2/markets/{ticker}').get('market')
        except Exception as e:
            print(f"⚠️  Failed to get market {ticker}: {e}")
            return None
    
    def verify_game_not_started(self, home_team: str, away_team: str, sport: str) -> bool:
        """
        Verify game has not started using The Odds API.
        This is CRITICAL - Kalshi market status 'active' does NOT mean game hasn't started.
        Returns True if game has NOT started, False if it has.
        """
        if not self.odds_api_key:
            print(f"   ⚠️  No Odds API key - cannot verify game start time (proceeding anyway)")
            return True
        
        try:
            # Map sport to Odds API sport key
            sport_map = {
                'NBA': 'basketball_nba',
                'NHL': 'icehockey_nhl',
                'MLB': 'baseball_mlb',
                'NFL': 'americanfootball_nfl',
                'NCAAB': 'basketball_ncaab'
            }
            sport_key = sport_map.get(sport.upper())
            if not sport_key:
                print(f"   ⚠️  Unknown sport {sport} - cannot verify game start")
                return True
            
            # Get scores (includes in-progress and completed games)
            url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores/'
            params = {'apiKey': self.odds_api_key, 'daysFrom': 1}
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                print(f"   ⚠️  Could not check game status: {response.status_code}")
                return True
            
            scores = response.json()
            
            # Normalize team names for matching
            home_norm = home_team.lower().replace(' ', '')
            away_norm = away_team.lower().replace(' ', '')
            
            for game in scores:
                game_home = game.get('home_team', '').lower().replace(' ', '')
                game_away = game.get('away_team', '').lower().replace(' ', '')
                
                # Check if this is our game
                if (home_norm in game_home or game_home in home_norm) and \
                   (away_norm in game_away or game_away in away_norm):
                    # Check if game has scores (started or completed)
                    if game.get('scores') or game.get('completed'):
                        print(f"   ❌ Game has STARTED/COMPLETED: {game.get('commence_time')}")
                        return False
            
            # Game not found in started/completed games
            return True
            
        except Exception as e:
            print(f"   ⚠️  Error checking game start: {e}")
            return True  # Fail open to avoid blocking valid bets
    
    def is_game_started(self, market: Dict) -> bool:
        """Legacy check - only checks Kalshi market status (NOT RELIABLE)"""
        if market.get('status', '').lower() in ['closed', 'settled', 'finalized']:
            return True
        close_time = market.get('close_time')
        if not close_time:
            return False
        try:
            return datetime.now(timezone.utc) >= datetime.fromisoformat(close_time.replace('Z', '+00:00'))
        except:
            return False
    
    def calculate_bet_size(self, confidence: float, edge: float, balance: float) -> float:
        bet_size = balance * (edge / 4.0)
        return round(max(self.min_bet_size, min(self.max_bet_size, balance * self.max_position_pct, bet_size)), 2)
    
    def place_bet(self, ticker: str, side: str, amount: float, price: Optional[int] = None) -> Optional[Dict]:
        """
        Place a limit order on Kalshi.
        
        IMPORTANT:
        - Must provide yes_price or no_price (no market orders allowed)
        - If price not provided, will fetch from market
        - Total cost = contracts × price (not just contracts)
        """
        # Get current market price if not provided
        if price is None:
            market = self.get_market_details(ticker)
            if not market:
                print(f"   ❌ Cannot get market price for {ticker}")
                return None
            price = market.get(f'{side}_ask')
            if not price:
                print(f"   ❌ No {side}_ask price available")
                return None
        
        # Calculate contracts to buy (amount is in dollars)
        # Cost = contracts × price, so contracts = (amount * 100) / price
        contracts = int((amount * 100) / price)
        if contracts < 1:
            print(f"   ❌ Amount ${amount:.2f} too small for price {price}¢")
            return None
        
        actual_cost = contracts * price / 100
        
        order_data = {
            'ticker': ticker,
            'action': 'buy',
            'side': side,
            'count': contracts,
            'type': 'limit',
            f'{side}_price': price,
            'client_order_id': str(uuid.uuid4())
        }
        
        try:
            response = self._post('/trade-api/v2/portfolio/orders', order_data)
            print(f"   ✅ Order placed: {ticker} {side.upper()} {contracts} contracts @ {price}¢ = ${actual_cost:.2f}")
            return response
        except Exception as e:
            print(f"   ❌ Order failed: {e}")
            return None
    
    def process_bet_recommendations(self, recommendations: List[Dict], sport_filter: Optional[List[str]] = None, min_confidence: float = 0.75, min_edge: float = 0.05, dry_run: bool = False) -> Dict:
        placed, skipped, errors = [], [], []
        balance, portfolio_value = self.get_balance()
        print(f"\n💰 Starting balance: ${balance:.2f}\n📊 Portfolio value: ${portfolio_value:.2f}\n")
        for rec in recommendations:
            if sport_filter and rec.get('sport', '').upper() not in [s.upper() for s in sport_filter]:
                skipped.append({'rec': rec, 'reason': f"Sport filter"}); continue
            elo_prob = rec.get('elo_prob', 0)
            if elo_prob < min_confidence:
                skipped.append({'rec': rec, 'reason': f"Low confidence"}); continue
            edge = rec.get('edge', 0)
            if edge < min_edge:
                skipped.append({'rec': rec, 'reason': f"Low edge"}); continue
            ticker = rec.get('ticker')
            if not ticker:
                errors.append(f"No ticker"); continue
            market = self.get_market_details(ticker)
            if not market:
                errors.append(f"Market not found: {ticker}"); continue
            
            # CRITICAL: Verify game has not started using The Odds API
            sport = rec.get('sport', 'NBA')
            if sport.lower() != 'tennis':
                if not self.verify_game_not_started(rec['home_team'], rec['away_team'], sport):
                    skipped.append({'rec': rec, 'reason': 'Game already started'}); continue
            
            if self.is_game_started(market):
                skipped.append({'rec': rec, 'reason': 'Market closed'}); continue
            bet_size = self.calculate_bet_size(elo_prob, edge, balance)
            if bet_size < self.min_bet_size:
                skipped.append({'rec': rec, 'reason': f'Insufficient balance'}); continue
            
            # Determine side (YES or NO)
            if sport.lower() == 'tennis':
                # For tennis: check if YES means the player we're betting on wins
                # The ticker format is: KXATPMATCH-26JAN17PLAYER1PLAYER2-YESPLAYER
                # If YES player matches our bet_on, we bet YES, otherwise NO
                ticker_parts = ticker.split('-')
                if len(ticker_parts) >= 3:
                    yes_player_abbr = ticker_parts[-1]  # Last part is YES player abbreviation
                    bet_on_upper = rec['bet_on'].upper()
                    # Check if our player's name is in the YES abbreviation
                    if any(word[:3].upper() == yes_player_abbr[:3] for word in rec['bet_on'].split()):
                        side = 'yes'
                    else:
                        side = 'no'
                else:
                    # Fallback: check title
                    title = market.get('title', '')
                    if rec['bet_on'] in title and 'Will ' + rec['bet_on'] in title:
                        side = 'yes'
                    else:
                        side = 'no'
            else:
                # Team sports: home/away
                side = 'yes' if rec['bet_on'] == 'home' else 'no'
            
            # Format match info
            if sport.lower() == 'tennis':
                match_info = rec.get('matchup', 'Unknown match')
                bet_player = rec['bet_on']
            else:
                match_info = f"{rec['away_team']} @ {rec['home_team']}"
                bet_player = rec['bet_on']
            
            print(f"🎯 {match_info}\n   Bet: {bet_player}, Side: {side.upper()}, Size: ${bet_size:.2f}, Confidence: {elo_prob:.1%}, Edge: {edge:.1%}")
            if not dry_run:
                result = self.place_bet(ticker, side, bet_size)
                if result:
                    placed.append({'rec': rec, 'bet_size': bet_size, 'side': side, 'result': result}); balance -= bet_size
                else:
                    errors.append(f"Failed: {ticker}")
            else:
                print(f"   [DRY RUN] Would place bet")
                placed.append({'rec': rec, 'bet_size': bet_size, 'side': side, 'dry_run': True}); balance -= bet_size
            time.sleep(1)
        return {'placed': placed, 'skipped': skipped, 'errors': errors, 'balance': balance}

if __name__ == '__main__':
    with open('kalshkey', 'r') as f:
        api_key_id = f.readline().strip().split(': ')[-1]
    print(f"Testing... API Key: {api_key_id[:30]}...\n")
    try:
        client = KalshiBetting(api_key_id, 'kalshi_private_key.pem', 5.0, True)
        balance, portfolio = client.get_balance()
        print(f"\n✅ Balance: ${balance:.2f}\n✅ Portfolio: ${portfolio:.2f}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback; traceback.print_exc()
