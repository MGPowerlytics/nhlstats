"""Provider-side fixtures: paired raw Kalshi tennis market lists for end-to-end tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .tennis_kalshi_samples import (
    build_tennis_kalshi_raw_market,
    build_tennis_kalshi_wta_raw_market,
)


def build_tennis_paired_raw_markets() -> list[dict[str, Any]]:
    """Build a paired ATP tennis matchup as raw Kalshi market list."""
    return [
        build_tennis_kalshi_raw_market("COB"),
        build_tennis_kalshi_raw_market("BLO"),
    ]


def build_tennis_single_sided_raw_markets() -> list[dict[str, Any]]:
    """Build a single-sided ATP market (only one binary present)."""
    return [build_tennis_kalshi_raw_market("COB")]


def build_tennis_wta_paired_raw_markets() -> list[dict[str, Any]]:
    """Build a paired WTA tennis matchup as raw Kalshi market list."""
    swi = build_tennis_kalshi_wta_raw_market()
    gau = deepcopy(swi)
    gau["ticker"] = "KXWTAMATCH-26APR07SWIGAU-GAU"
    gau["yes_sub_title"] = "Coco Gauff"
    gau["no_sub_title"] = "Coco Gauff"
    gau["yes_ask"] = 30
    gau["no_ask"] = 70
    gau["title"] = "Will Coco Gauff win the Swiatek vs Gauff : Round Of 16 match?"
    return [swi, gau]
