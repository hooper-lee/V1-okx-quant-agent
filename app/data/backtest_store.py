from __future__ import annotations

from datetime import datetime
from typing import Optional


class BacktestStore:
    def __init__(self) -> None:
        self._items: list[dict] = []

    def save(self, item: dict) -> dict:
        self._items.insert(0, item)
        return item

    def list_all(self) -> list[dict]:
        return self._items.copy()

    def get(self, run_id: str) -> Optional[dict]:
        for item in self._items:
            if item.get("run_id") == run_id:
                return item
        return None

    def delete(self, run_id: str) -> Optional[dict]:
        for index, item in enumerate(self._items):
            if item.get("run_id") == run_id:
                return self._items.pop(index)
        return None

    def compare(self, run_ids: list[str]) -> dict:
        items = [item for item in self._items if item.get("run_id") in run_ids]
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "items": items,
            "summary": [
                {
                    "run_id": item.get("run_id"),
                    "label": item.get("label"),
                    "strategy_name": item.get("strategy_name"),
                    "symbol": item.get("symbol"),
                    "timeframe": item.get("timeframe"),
                    "total_return_pct": item.get("total_return_pct"),
                    "max_drawdown_pct": item.get("max_drawdown_pct"),
                    "sharpe_ratio": item.get("sharpe_ratio"),
                    "trade_count": item.get("trade_count"),
                    "win_rate_pct": item.get("win_rate_pct"),
                }
                for item in items
            ],
        }
