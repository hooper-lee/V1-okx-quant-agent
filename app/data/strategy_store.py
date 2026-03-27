from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


DEFAULT_STRATEGIES = [
    {
        "name": "mean_reversion",
        "created_at": "2026-05-05 18:00:00",
        "type": "reversal",
        "risk_preference": "balanced",
        "description": "基于 RSI 的均值回归策略。",
        "execution_notes": "优先在 RSI 进入极值区间后观察价格回归，再结合止损阈值分批执行。",
        "config": {
            "symbol": "ETH-USDT-SWAP",
            "timeframe": "4h",
            "target_capital": 8000.0,
            "target_horizon_days": 45,
            "leverage": 1.5,
            "entry_allocation_pct": 18.0,
            "max_position_pct": 42.0,
            "max_drawdown_limit_pct": 10.0,
            "margin_mode": "cross",
            "fast_period": 6,
            "slow_period": 18,
            "rsi_period": 14,
            "take_profit_pct": 6.0,
            "stop_loss_pct": 2.5,
            "risk_limit_pct": 1.5,
        },
    },
    {
        "name": "sma_crossover",
        "created_at": "2026-05-05 18:00:00",
        "type": "trend",
        "risk_preference": "balanced",
        "description": "基于均线交叉的趋势策略。",
        "execution_notes": "短周期均线上穿慢线后分批跟随，若 MACD 与量能同步转弱则优先收缩仓位。",
        "config": {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1h",
            "target_capital": 12000.0,
            "target_horizon_days": 21,
            "leverage": 2.0,
            "entry_allocation_pct": 24.0,
            "max_position_pct": 55.0,
            "max_drawdown_limit_pct": 12.0,
            "margin_mode": "cross",
            "fast_period": 7,
            "slow_period": 20,
            "rsi_period": 14,
            "take_profit_pct": 8.0,
            "stop_loss_pct": 3.0,
            "risk_limit_pct": 2.0,
        },
    },
    {
        "name": "news_sentiment",
        "created_at": "2026-05-04 11:30:00",
        "type": "hybrid",
        "risk_preference": "balanced",
        "description": "结合新闻情绪和技术指标的混合策略。",
        "execution_notes": "先确认新闻情绪与技术信号同向，再按风险阈值逐步建仓，情绪反转时及时减仓。",
        "config": {
            "symbol": "SOL-USDT-SWAP",
            "timeframe": "1d",
            "target_capital": 15000.0,
            "target_horizon_days": 90,
            "leverage": 1.2,
            "entry_allocation_pct": 15.0,
            "max_position_pct": 35.0,
            "max_drawdown_limit_pct": 9.0,
            "margin_mode": "isolated",
            "fast_period": 10,
            "slow_period": 30,
            "rsi_period": 21,
            "take_profit_pct": 10.0,
            "stop_loss_pct": 4.0,
            "risk_limit_pct": 1.8,
        },
    },
]


class StrategyStore:
    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self.store_path.exists():
            self._persist(DEFAULT_STRATEGIES)
            return [*DEFAULT_STRATEGIES]
        try:
            items = json.loads(self.store_path.read_text(encoding="utf-8"))
            if isinstance(items, list) and items:
                return items
        except Exception:
            pass
        self._persist(DEFAULT_STRATEGIES)
        return [*DEFAULT_STRATEGIES]

    def _persist(self, items: list[dict]) -> None:
        self.store_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_all(self) -> list[dict]:
        return [*self._items]

    def get(self, name: str) -> Optional[dict]:
        for item in self._items:
            if item["name"] == name:
                return item
        return None

    def add(self, item: dict) -> dict:
        existing = self.get(item["name"])
        if existing is not None:
            raise ValueError(f"Strategy {item['name']} already exists")
        self._items.insert(0, item)
        self._persist(self._items)
        return item

    def update(self, name: str, payload: dict) -> Optional[dict]:
        item = self.get(name)
        if item is None:
            return None
        item.update(payload)
        self._persist(self._items)
        return item
