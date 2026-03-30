"""
TDD tests for fetch_tennis_markets() migration from TheOddsAPI to Kalshi SDK.

Tests cover:
- fetch_tennis_markets() fetches all 4 ATP/WTA series via KalshiAPI
- Graceful handling of empty series, partial failures, full failure
- TennisTickerParser.parse() with actual Kalshi ticker/title formats
- _save_markets_to_db (save_to_db) integration with sport="tennis"
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

import plugins.kalshi_markets as km
from plugins.kalshi_markets import (
    TennisTickerParser,
    fetch_tennis_markets,
    SPORT_SERIES,
)

# ---------------------------------------------------------------------------
# Fixtures / sample data
# ---------------------------------------------------------------------------

SAMPLE_ATP_MARKET = {
    "ticker": "KXATPMATCH-26JAN20ALCHAN-ALC",
    "title": "Will Carlos Alcaraz win the Alcaraz vs Chan : Round Of 64 match?",
    "status": "active",
    "yes_bid": 70,
    "yes_ask": 72,
    "last_price": 71,
    "close_time": "2026-01-20T10:00:00Z",
}

SAMPLE_WTA_MARKET = {
    "ticker": "KXWTAMATCH-26JAN20GAUDAN-GAU",
    "title": "Will Coco Gauff win the Gauff vs Dan : Round Of 64 match?",
    "status": "active",
    "yes_bid": 60,
    "yes_ask": 62,
    "last_price": 61,
    "close_time": "2026-01-20T12:00:00Z",
}

SAMPLE_CHALLENGER_MARKET = {
    "ticker": "KXATPCHALLENGERMATCH-26JAN20RIBBLA-RIB",
    "title": "Will Michele Ribecai win the Ribecai vs Blanch : Round Of 16 match?",
    "status": "active",
    "yes_bid": 55,
    "yes_ask": 57,
    "last_price": 56,
    "close_time": "2026-01-20T14:00:00Z",
}

SAMPLE_WTA_CHALLENGER_MARKET = {
    "ticker": "KXWTACHALLENGERMATCH-26JAN21BOUSWI-SWI",
    "title": "Will Iga Swiatek win the Bouzkova vs Swiatek match?",
    "status": "active",
    "yes_bid": 80,
    "yes_ask": 82,
    "last_price": 81,
    "close_time": "2026-01-21T09:00:00Z",
}


def _make_api_mock(series_data: dict) -> MagicMock:
    """Build a KalshiAPI mock that returns markets keyed by series_ticker.

    Args:
        series_data: Mapping of series_ticker → list of market dicts to return.

    Returns:
        Configured MagicMock for KalshiAPI instance.
    """
    api_mock = MagicMock()

    def _get_markets(series_ticker=None, limit=100, **kwargs):
        markets = series_data.get(series_ticker, [])
        return {"markets": markets}

    api_mock.get_markets.side_effect = _get_markets
    # get_market returns None so _get_detailed_market falls back to basic data
    api_mock.get_market.return_value = None
    return api_mock


# ---------------------------------------------------------------------------
# SPORT_SERIES sanity check
# ---------------------------------------------------------------------------


class TestTennisSportSeries:
    """Verify tennis is registered with all 4 Kalshi series tickers."""

    def test_tennis_has_four_series_tickers(self):
        assert "tennis" in SPORT_SERIES
        assert len(SPORT_SERIES["tennis"]) == 4

    def test_tennis_series_tickers_are_correct(self):
        expected = {
            "KXATPMATCH",
            "KXWTAMATCH",
            "KXATPCHALLENGERMATCH",
            "KXWTACHALLENGERMATCH",
        }
        assert set(SPORT_SERIES["tennis"]) == expected


# ---------------------------------------------------------------------------
# TennisTickerParser tests
# ---------------------------------------------------------------------------


class TestTennisTickerParser:
    """Test TennisTickerParser.parse() with real Kalshi title formats."""

    def setup_method(self):
        self.parser = TennisTickerParser()

    def test_parse_atp_market_with_colon_format(self):
        """Title: 'Will X win the A vs B : Round Of 64 match?'"""
        ticker = "KXATPMATCH-26JAN20ALCHAN-ALC"
        title = "Will Carlos Alcaraz win the Alcaraz vs Chan : Round Of 64 match?"
        result = self.parser.parse(ticker, title)
        assert result is not None
        home, away, date = result
        assert home == "Alcaraz"
        assert away == "Chan"
        assert date == "2026-01-20"

    def test_parse_wta_market_with_plain_match_format(self):
        """Title: 'Will X win the A vs B match?'"""
        ticker = "KXWTAMATCH-26JAN20BOUSWI-SWI"
        title = "Will Iga Swiatek win the Bouzkova vs Swiatek match?"
        result = self.parser.parse(ticker, title)
        assert result is not None
        home, away, date = result
        assert home == "Bouzkova"
        assert away == "Swiatek"
        assert date == "2026-01-20"

    def test_parse_challenger_market(self):
        ticker = "KXATPCHALLENGERMATCH-26JAN20RIBBLA-RIB"
        title = "Will Michele Ribecai win the Ribecai vs Blanch : Round Of 16 match?"
        result = self.parser.parse(ticker, title)
        assert result is not None
        home, away, date = result
        assert home == "Ribecai"
        assert away == "Blanch"
        assert date == "2026-01-20"

    def test_parse_returns_none_when_no_vs_in_title(self):
        ticker = "KXATPMATCH-26JAN20ALCHAN-ALC"
        title = "Some unrelated market title"
        result = self.parser.parse(ticker, title)
        assert result is None

    def test_parse_date_extraction_from_ticker(self):
        """Date should be parsed from YYMMMDD portion of ticker."""
        ticker = "KXWTAMATCH-26MAR15NAVNOV-NOV"
        title = "Will Novak Navratilova win the Navratilova vs Novakova match?"
        result = self.parser.parse(ticker, title)
        assert result is not None
        _, _, date = result
        assert date == "2026-03-15"

    def test_parse_returns_none_for_empty_ticker(self):
        result = self.parser.parse("", "")
        assert result is None


# ---------------------------------------------------------------------------
# fetch_tennis_markets() tests
# ---------------------------------------------------------------------------


class TestFetchTennisMarkets:
    """Test the replaced fetch_tennis_markets() using Kalshi SDK."""

    def _patch_deps(self, series_data: dict):
        """Context manager helper: patches credentials + KalshiAPI constructor."""
        api_instance = _make_api_mock(series_data)

        creds_patch = patch.object(
            km, "load_kalshi_credentials", return_value=("test_key_id", "test_pem")
        )
        api_patch = patch.object(km, "KalshiAPI", return_value=api_instance)
        save_patch = patch.object(km, "save_to_db", return_value=1)
        return creds_patch, api_patch, save_patch, api_instance

    def test_fetches_from_kalshi_not_the_odds_api(self):
        """fetch_tennis_markets must not instantiate TheOddsAPI."""
        series_data = {"KXATPMATCH": [SAMPLE_ATP_MARKET]}
        creds_p, api_p, save_p, _ = self._patch_deps(series_data)

        with creds_p, api_p, save_p, patch.object(
            km, "TheOddsAPI"
        ) as odds_mock:
            fetch_tennis_markets()
            odds_mock.assert_not_called()

    def test_queries_all_four_series_tickers(self):
        """All 4 series tickers must be queried."""
        series_data = {
            "KXATPMATCH": [SAMPLE_ATP_MARKET],
            "KXWTAMATCH": [SAMPLE_WTA_MARKET],
            "KXATPCHALLENGERMATCH": [SAMPLE_CHALLENGER_MARKET],
            "KXWTACHALLENGERMATCH": [SAMPLE_WTA_CHALLENGER_MARKET],
        }
        creds_p, api_p, save_p, api_instance = self._patch_deps(series_data)

        with creds_p, api_p, save_p:
            result = fetch_tennis_markets()

        queried_series = {
            c.kwargs.get("series_ticker") or c.args[0]
            for c in api_instance.get_markets.call_args_list
            if (c.args or c.kwargs)
        }
        for expected in SPORT_SERIES["tennis"]:
            assert expected in queried_series, f"{expected} was not queried"
        assert len(result) == 4

    def test_returns_all_markets_from_all_series(self):
        """Return value must aggregate markets from all series."""
        series_data = {
            "KXATPMATCH": [SAMPLE_ATP_MARKET],
            "KXWTAMATCH": [SAMPLE_WTA_MARKET],
            "KXATPCHALLENGERMATCH": [],
            "KXWTACHALLENGERMATCH": [],
        }
        creds_p, api_p, save_p, _ = self._patch_deps(series_data)

        with creds_p, api_p, save_p:
            result = fetch_tennis_markets()

        assert len(result) == 2
        tickers = {m["ticker"] for m in result}
        assert SAMPLE_ATP_MARKET["ticker"] in tickers
        assert SAMPLE_WTA_MARKET["ticker"] in tickers

    def test_one_series_empty_others_succeed(self):
        """When one series has no markets, the rest still succeed."""
        series_data = {
            "KXATPMATCH": [],  # No ATP markets (between tournaments)
            "KXWTAMATCH": [SAMPLE_WTA_MARKET],
            "KXATPCHALLENGERMATCH": [SAMPLE_CHALLENGER_MARKET],
            "KXWTACHALLENGERMATCH": [],
        }
        creds_p, api_p, save_p, _ = self._patch_deps(series_data)

        with creds_p, api_p, save_p:
            result = fetch_tennis_markets()

        assert len(result) == 2
        tickers = {m["ticker"] for m in result}
        assert SAMPLE_WTA_MARKET["ticker"] in tickers
        assert SAMPLE_CHALLENGER_MARKET["ticker"] in tickers

    def test_one_series_raises_exception_others_succeed(self):
        """An exception in one series must not block the others."""
        call_count = {"n": 0}

        def _get_markets_raises_once(series_ticker=None, limit=100, **kwargs):
            call_count["n"] += 1
            if series_ticker == "KXATPMATCH":
                raise RuntimeError("Simulated API error for ATP")
            return {"markets": [SAMPLE_WTA_MARKET] if series_ticker == "KXWTAMATCH" else []}

        api_instance = MagicMock()
        api_instance.get_markets.side_effect = _get_markets_raises_once
        api_instance.get_market.return_value = None

        with (
            patch.object(km, "load_kalshi_credentials", return_value=("k", "p")),
            patch.object(km, "KalshiAPI", return_value=api_instance),
            patch.object(km, "save_to_db", return_value=1),
        ):
            result = fetch_tennis_markets()

        # Should not propagate exception, and should return the WTA market
        assert isinstance(result, list)
        assert SAMPLE_WTA_MARKET["ticker"] in {m["ticker"] for m in result}

    def test_all_series_fail_returns_empty_list_no_exception(self):
        """If every series raises an exception, return [] without raising."""
        api_instance = MagicMock()
        api_instance.get_markets.side_effect = RuntimeError("All down")
        api_instance.get_market.return_value = None

        with (
            patch.object(km, "load_kalshi_credentials", return_value=("k", "p")),
            patch.object(km, "KalshiAPI", return_value=api_instance),
            patch.object(km, "save_to_db", return_value=0),
        ):
            result = fetch_tennis_markets()

        assert result == []

    def test_credential_failure_returns_empty_list(self):
        """Credential loading failure must return [] without raising."""
        with patch.object(
            km, "load_kalshi_credentials", side_effect=FileNotFoundError("no creds")
        ):
            result = fetch_tennis_markets()

        assert result == []

    def test_kalshi_unavailable_returns_empty_list(self):
        """When kalshi_python is not installed, return [] gracefully."""
        original = km.KALSHI_AVAILABLE
        km.KALSHI_AVAILABLE = False
        try:
            result = fetch_tennis_markets()
        finally:
            km.KALSHI_AVAILABLE = original

        assert result == []

    def test_save_to_db_called_with_tennis_sport(self):
        """save_to_db must be called with sport='tennis'."""
        series_data = {
            "KXATPMATCH": [SAMPLE_ATP_MARKET],
            "KXWTAMATCH": [],
            "KXATPCHALLENGERMATCH": [],
            "KXWTACHALLENGERMATCH": [],
        }
        creds_p, api_p, save_p, _ = self._patch_deps(series_data)

        with creds_p, api_p, save_p as mock_save:
            fetch_tennis_markets()

        # save_to_db should have been called with 'tennis' as sport
        assert mock_save.called
        call_args = mock_save.call_args
        assert call_args[0][0] == "tennis" or call_args[1].get("sport") == "tennis"

    def test_date_str_arg_accepted_without_error(self):
        """date_str param must be accepted (interface compat) even if unused."""
        series_data = {"KXATPMATCH": [SAMPLE_ATP_MARKET]}
        creds_p, api_p, save_p, _ = self._patch_deps(series_data)

        with creds_p, api_p, save_p:
            # Should not raise regardless of date_str value
            result = fetch_tennis_markets(date_str="2026-01-20")

        assert isinstance(result, list)

    def test_returns_list_type(self):
        """Return value must always be a list."""
        series_data = {}
        api_instance = MagicMock()
        api_instance.get_markets.return_value = {"markets": []}
        api_instance.get_market.return_value = None

        with (
            patch.object(km, "load_kalshi_credentials", return_value=("k", "p")),
            patch.object(km, "KalshiAPI", return_value=api_instance),
            patch.object(km, "save_to_db", return_value=0),
        ):
            result = fetch_tennis_markets()

        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Integration: save_to_db with tennis sport (mocked DB)
# ---------------------------------------------------------------------------


class TestTennisSaveToDb:
    """Verify save_to_db handles tennis market dicts without error."""

    def test_save_to_db_parses_atp_market(self):
        """save_to_db should parse ATP market without raising (mocked DB)."""
        db_mock = MagicMock()
        db_mock.execute.return_value = None

        with patch("plugins.kalshi_markets.DBManager", MagicMock()), patch(
            "plugins.database_schema_manager.DatabaseSchemaManager"
        ) as schema_mock:
            schema_mock.return_value.initialize_schema.return_value = None

            # Should not raise even if game upsert is mocked
            with patch.object(km, "_upsert_game", return_value="TENNIS_20260120_ALCARAZ_CHAN"), patch.object(
                km, "_upsert_odds", return_value=True
            ):
                count = km.save_to_db("tennis", [SAMPLE_ATP_MARKET], db_manager=db_mock)

        assert count >= 0  # May be 0 if parse fails, but must not raise

    def test_save_to_db_with_unresolvable_market_logs_warning_not_raise(self):
        """Markets that fail parsing should be skipped, not crash the function."""
        bad_market = {"ticker": "KXATPMATCH-BAD", "title": "unparseable", "status": "active"}
        db_mock = MagicMock()

        with patch("plugins.database_schema_manager.DatabaseSchemaManager") as schema_mock:
            schema_mock.return_value.initialize_schema.return_value = None
            count = km.save_to_db("tennis", [bad_market], db_manager=db_mock)

        assert count == 0  # skipped, not crashed
