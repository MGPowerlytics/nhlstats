"""Lazy exports for optional box-score fetchers."""

from __future__ import annotations

import importlib
import logging as _logging

_log = _logging.getLogger(__name__)

# Base class is mandatory; everything else is best-effort so a single missing
# optional dependency (e.g. nba_api, nfl_data_py) cannot break the entire
# package and, by extension, every Airflow task or DAG that touches this
# package transitively.
from plugins.stats.base import BoxScoreFetcher

__all__ = ["BoxScoreFetcher", "resolve_fetcher_class"]

_OPTIONAL_FETCHERS = {
    "NBABoxScoreFetcher": "nba_box_score",
    "NHLBoxScoreFetcher": "nhl_box_score",
    "MLBBoxScoreFetcher": "mlb_box_score",
    "NFLBoxScoreFetcher": "nfl_box_score",
    "SoccerBoxScoreFetcher": "soccer_box_score",
    "CBBBoxScoreFetcher": "cbb_box_score",
    "TennisBoxScoreFetcher": "tennis_box_score",
}

_FAILED_OPTIONAL_FETCHERS: dict[str, Exception] = {}


def _import_optional_fetcher(attr: str):
    """Import and cache an optional fetcher class."""
    if attr in globals():
        return globals()[attr]

    module_name = _OPTIONAL_FETCHERS[attr]

    if attr in _FAILED_OPTIONAL_FETCHERS:
        exc = _FAILED_OPTIONAL_FETCHERS[attr]
        raise ImportError(
            f"Optional box-score fetcher {attr} is unavailable"
        ) from exc

    try:
        module = importlib.import_module(f"plugins.stats.{module_name}")
        fetcher_class = getattr(module, attr)
    except Exception as exc:  # noqa: BLE001 - optional dependencies are best-effort
        _FAILED_OPTIONAL_FETCHERS[attr] = exc
        _log.warning(
            "Optional box-score fetcher %s unavailable: %s: %s",
            attr,
            type(exc).__name__,
            exc,
        )
        raise ImportError(
            f"Optional box-score fetcher {attr} is unavailable"
        ) from exc

    globals()[attr] = fetcher_class
    _FAILED_OPTIONAL_FETCHERS.pop(attr, None)
    return fetcher_class


def resolve_fetcher_class(attr: str):
    """Return the requested box-score fetcher class."""
    if attr not in _OPTIONAL_FETCHERS:
        raise ValueError(f"Unknown box-score fetcher: {attr}")

    return _import_optional_fetcher(attr)


def __getattr__(attr: str):
    """Resolve optional fetchers lazily for direct attribute imports."""
    if attr not in _OPTIONAL_FETCHERS:
        raise AttributeError(f"module {__name__!r} has no attribute {attr!r}")

    try:
        return _import_optional_fetcher(attr)
    except ImportError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {attr!r}"
        ) from exc
