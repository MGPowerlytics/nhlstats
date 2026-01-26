"""
Mock Kalshi API for integration testing.
"""

from datetime import datetime


class MockKalshiAPI:
    def __init__(self):
        self.markets = self._create_sample_markets()
        self.balance = 1000.0
        self.orders = []
        self.order_counter = 1

    def _create_sample_markets(self):
        markets = []

        nba_markets = [
            {
                "ticker": "KXNBAGAME-260124-LALDAL-YES",
                "title": "Will the Los Angeles Lakers defeat the Dallas Mavericks on January 24, 2026?",
                "status": "active",
                "yes_ask": 65,
                "yes_bid": 63,
                "no_ask": 37,
                "no_bid": 35,
                "close_time": "2026-01-24T23:00:00Z",
                "volume": 1500,
                "open_interest": 2500,
            },
            {
                "ticker": "KXNBAGAME-260124-BOSNYK-YES",
                "title": "Will the Boston Celtics defeat the New York Knicks on January 24, 2026?",
                "status": "active",
                "yes_ask": 72,
                "yes_bid": 70,
                "no_ask": 30,
                "no_bid": 28,
                "close_time": "2026-01-24T23:00:00Z",
                "volume": 1200,
                "open_interest": 1800,
            },
        ]

        nhl_markets = [
            {
                "ticker": "KXNHLGAME-260124-TORBOS-YES",
                "title": "Will the Toronto Maple Leafs defeat the Boston Bruins on January 24, 2026?",
                "status": "active",
                "yes_ask": 58,
                "yes_bid": 56,
                "no_ask": 44,
                "no_bid": 42,
                "close_time": "2026-01-24T23:00:00Z",
                "volume": 800,
                "open_interest": 1200,
            }
        ]

        tennis_markets = [
            {
                "ticker": "KXATPMATCH-260124-DJOFED-YES",
                "title": "Will Novak Djokovic defeat Roger Federer on January 24, 2026?",
                "status": "active",
                "yes_ask": 68,
                "yes_bid": 66,
                "no_ask": 34,
                "no_bid": 32,
                "close_time": "2026-01-24T18:00:00Z",
                "volume": 500,
                "open_interest": 800,
            }
        ]

        markets.extend(nba_markets)
        markets.extend(nhl_markets)
        markets.extend(tennis_markets)

        return markets

    def get_markets(self, series_ticker=None, status="active", limit=100):
        filtered_markets = []

        for market in self.markets:
            if market.get("status") != status:
                continue

            if series_ticker and not market["ticker"].startswith(series_ticker):
                continue

            filtered_markets.append(market)

        return {
            "markets": filtered_markets[:limit],
            "cursor": None,
            "has_more": len(filtered_markets) > limit,
        }

    def get_market_details(self, ticker):
        for market in self.markets:
            if market["ticker"] == ticker:
                return market
        return None

    def get_balance(self):
        return {
            "balance": self.balance,
            "available_balance": self.balance * 0.9,
            "total_balance": self.balance,
            "currency": "USD",
        }

    def place_order(self, ticker, side, amount, price):
        market = self.get_market_details(ticker)
        if not market:
            return {"error": "Market not found"}

        if market["status"] != "active":
            return {"error": f"Market not active (status: {market['status']})"}

        order_cost = amount
        if self.balance < order_cost:
            return {"error": "Insufficient balance"}

        order_id = f"order_{self.order_counter}"
        self.order_counter += 1

        order = {
            "order_id": order_id,
            "ticker": ticker,
            "side": side,
            "amount": amount,
            "price": price,
            "status": "filled",
            "filled_amount": amount,
            "filled_price": price,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        self.orders.append(order)
        self.balance -= order_cost

        return {"order": order, "message": "Order placed successfully"}

    def get_order(self, order_id):
        for order in self.orders:
            if order["order_id"] == order_id:
                return order
        return None


class MockKalshiBetting:
    def __init__(self, api_key_id="test_key", private_key_path="test_key.pem"):
        self.api = MockKalshiAPI()
        self.api_key_id = api_key_id

    def get_balance(self):
        balance_data = self.api.get_balance()
        return balance_data["balance"], balance_data["available_balance"]

    def get_market_details(self, ticker):
        return self.api.get_market_details(ticker)

    def place_bet(self, ticker, side, amount, price, trade_date):
        result = self.api.place_order(ticker, side, amount, price)
        if "error" in result:
            return None
        return result.get("order")

    def get_markets(self, series_ticker, limit=100):
        result = self.api.get_markets(series_ticker=series_ticker, limit=limit)
        return result.get("markets", [])


def create_mock_kalshi_client():
    return MockKalshiBetting()


if __name__ == "__main__":
    api = MockKalshiAPI()

    print("Testing Mock Kalshi API")
    print("=" * 50)

    markets = api.get_markets(series_ticker="KXNBAGAME")
    print(f"NBA Markets: {len(markets['markets'])}")

    market = api.get_market_details("KXNBAGAME-260124-LALDAL-YES")
    print(f"Market details: {market['title'] if market else 'Not found'}")

    balance = api.get_balance()
    print(f"Balance: ${balance['balance']:.2f}")

    order = api.place_order(
        ticker="KXNBAGAME-260124-LALDAL-YES", side="yes", amount=10.0, price=65
    )
    print(
        f"Order placed: {order.get('order', {}).get('order_id') if 'order' in order else 'Failed'}"
    )

    print("=" * 50)
    print("Mock API test complete")
