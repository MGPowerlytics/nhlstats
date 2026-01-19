"""Order deduplication utilities.

Purpose:
- Prevent placing multiple orders on the same Kalshi ticker.
- Prevent placing orders on both sides (YES/NO) of the same ticker.

Implementation:
- Uses an atomic filesystem lock per ticker.
- This works across processes and across retries.

The lock is intentionally per ticker (not per side, and not per date). If a lock
exists, no further bets can be placed on that ticker regardless of side or day.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ReservationResult:
    """Result of attempting to reserve a ticker for ordering."""

    reserved: bool
    reason: str
    lock_path: Path


class OrderDeduper:
    """Cross-process-safe deduper for Kalshi order placement."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def _lock_path(self, *, ticker: str) -> Path:
        safe_ticker = ticker.replace("/", "_")
        return self._base_dir / "tickers" / f"{safe_ticker}.lock.json"

    def reserve(self, *, trade_date: str, ticker: str, side: str, metadata: Optional[Dict[str, Any]] = None) -> ReservationResult:
        """Reserve a ticker for a single order.

        Args:
            trade_date: YYYY-MM-DD informational only (lock is per ticker).
            ticker: Kalshi ticker.
            side: yes|no.
            metadata: Optional extra JSON to persist.

        Returns:
            ReservationResult indicating whether reservation succeeded.
        """

        lock_path = self._lock_path(ticker=ticker)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        payload: Dict[str, Any] = {
            "ticker": ticker,
            "side": side,
            "trade_date": trade_date,
            "reserved_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            payload["metadata"] = metadata

        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(lock_path), flags)
        except FileExistsError:
            return ReservationResult(reserved=False, reason="Already reserved", lock_path=lock_path)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            # If writing fails after creation, remove the lock to avoid permanent blockage.
            try:
                lock_path.unlink(missing_ok=True)  # type: ignore[call-arg]
            except Exception:
                pass
            raise

        return ReservationResult(reserved=True, reason="Reserved", lock_path=lock_path)
