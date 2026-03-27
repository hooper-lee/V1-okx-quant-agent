from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from app.integrations.okx_client import OKXClient


TIMEFRAME_TO_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


class MarketDataService:
    def __init__(self, settings, runtime_config_service=None) -> None:
        self.settings = settings
        self.okx_client = OKXClient(settings=settings, runtime_config_service=runtime_config_service)

    def get_candles(self, symbol: str, timeframe: str, limit: int = 50) -> list[dict]:
        if self.settings.use_live_services:
            candles = self._get_okx_candles(symbol=symbol, timeframe=timeframe, limit=limit)
            if candles:
                return candles
        return self._get_demo_candles(symbol=symbol, timeframe=timeframe, limit=limit)

    def get_ticker(self, symbol: str) -> dict:
        if self.settings.use_live_services:
            try:
                ticker = self.okx_client.fetch_ticker(symbol)
                if ticker:
                    return ticker
            except Exception:
                pass

        candles = self._get_demo_candles(symbol=symbol, timeframe="1h", limit=2)
        last = candles[-1]["close"]
        return {"symbol": symbol, "last": last, "bid": last - 5, "ask": last + 5, "source": "demo"}

    def _get_okx_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        try:
            return self.okx_client.fetch_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        except Exception:
            return []

    def _get_demo_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        minutes = TIMEFRAME_TO_MINUTES.get(timeframe, 60)
        now = datetime.now(timezone.utc)
        candles: list[dict] = []
        base_price = 85000.0

        for index in range(limit):
            ts = now - timedelta(minutes=minutes * (limit - index))
            drift = index * 45
            wave = math.sin(index / 2.8) * 120
            close = base_price + drift + wave
            open_price = close - 15 - math.cos(index / 3) * 12
            high = close + 40 + abs(math.sin(index)) * 20
            low = close - 55 - abs(math.cos(index / 2)) * 18
            volume = 100 + index * 3
            candles.append(
                {
                    "timestamp": ts.isoformat(),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": round(volume, 2),
                }
            )
        return candles
