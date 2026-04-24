"""Tests for the plugins.stats optional import boundary."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from unittest.mock import patch

import pytest


def _reload_stats_module():
    import plugins.stats as stats

    return importlib.reload(stats)


def test_resolve_fetcher_class_imports_fetchers_lazily(monkeypatch):
    """Optional fetchers should be imported only when explicitly resolved."""
    stats = _reload_stats_module()

    class FakeFetcher:
        pass

    fake_module = ModuleType("plugins.stats.fake_optional_fetcher")
    fake_module.FakeFetcher = FakeFetcher

    monkeypatch.setitem(
        stats._OPTIONAL_FETCHERS, "FakeFetcher", "fake_optional_fetcher"
    )
    monkeypatch.delitem(stats.__dict__, "FakeFetcher", raising=False)
    stats._FAILED_OPTIONAL_FETCHERS.pop("FakeFetcher", None)

    original_import_module = stats.importlib.import_module

    def fake_import_module(module_name: str):
        if module_name == "plugins.stats.fake_optional_fetcher":
            return fake_module
        return original_import_module(module_name)

    monkeypatch.setattr(stats.importlib, "import_module", fake_import_module)

    resolved = stats.resolve_fetcher_class("FakeFetcher")

    assert resolved is FakeFetcher
    assert getattr(stats, "FakeFetcher") is FakeFetcher


def test_resolve_fetcher_class_raises_on_missing_optional_dependency(monkeypatch):
    """Missing optional SDKs should raise ImportError only on resolution."""
    stats = _reload_stats_module()

    monkeypatch.setitem(stats._OPTIONAL_FETCHERS, "BrokenFetcher", "broken_fetcher")
    monkeypatch.delitem(stats.__dict__, "BrokenFetcher", raising=False)
    stats._FAILED_OPTIONAL_FETCHERS.pop("BrokenFetcher", None)

    original_import_module = stats.importlib.import_module

    def fake_import_module(module_name: str):
        if module_name == "plugins.stats.broken_fetcher":
            raise ModuleNotFoundError("optional sdk missing")
        return original_import_module(module_name)

    monkeypatch.setattr(stats.importlib, "import_module", fake_import_module)

    with pytest.raises(ImportError, match="BrokenFetcher"):
        stats.resolve_fetcher_class("BrokenFetcher")


def test_backfill_script_import_does_not_resolve_optional_fetchers():
    """Importing the backfill script should not resolve optional fetchers."""
    with patch("plugins.db_manager.DBManager"), patch(
        "plugins.stats.resolve_fetcher_class",
        side_effect=AssertionError("resolve_fetcher_class should not run at import"),
    ):
        module = sys.modules.get("scripts.backfill_team_game_stats")
        if module is None:
            module = importlib.import_module("scripts.backfill_team_game_stats")
        reloaded = importlib.reload(module)

    assert reloaded is not None
