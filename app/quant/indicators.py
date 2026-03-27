from __future__ import annotations

import math


class TechnicalIndicatorService:
    def calculate(self, candles: list[dict]) -> dict:
        closes = [float(item["close"]) for item in candles]
        highs = [float(item["high"]) for item in candles]
        lows = [float(item["low"]) for item in candles]
        volumes = [float(item.get("volume", 0.0)) for item in candles]

        sma_fast = self._sma(closes, period=7)
        sma_slow = self._sma(closes, period=20)
        ema_fast = self._ema(closes, period=12)
        ema_slow = self._ema(closes, period=26)
        rsi = self._rsi(closes, period=14)
        macd_line, macd_signal, macd_histogram = self._macd(closes)
        bollinger_middle, bollinger_upper, bollinger_lower = self._bollinger_bands(closes, period=20, std_multiplier=2.0)
        atr = self._atr(highs, lows, closes, period=14)
        volume_ma = self._sma(volumes, period=20)

        return {
            "sma_fast": round(sma_fast, 4),
            "sma_slow": round(sma_slow, 4),
            "ema_fast": round(ema_fast, 4),
            "ema_slow": round(ema_slow, 4),
            "rsi": round(rsi, 4),
            "macd": {
                "line": round(macd_line, 4),
                "signal": round(macd_signal, 4),
                "histogram": round(macd_histogram, 4),
            },
            "bollinger_bands": {
                "middle": round(bollinger_middle, 4),
                "upper": round(bollinger_upper, 4),
                "lower": round(bollinger_lower, 4),
            },
            "atr": round(atr, 4),
            "volume_ma": round(volume_ma, 4),
            "last_close": round(closes[-1], 4) if closes else 0.0,
            "last_volume": round(volumes[-1], 4) if volumes else 0.0,
        }

    def _sma(self, values: list[float], period: int) -> float:
        if not values:
            return 0.0
        window = values[-period:] if len(values) >= period else values
        return sum(window) / len(window)

    def _ema(self, values: list[float], period: int) -> float:
        if not values:
            return 0.0
        multiplier = 2 / (period + 1)
        ema = values[0]
        for value in values[1:]:
            ema = (value - ema) * multiplier + ema
        return ema

    def _rsi(self, values: list[float], period: int) -> float:
        if len(values) < 2:
            return 50.0

        changes = [values[index] - values[index - 1] for index in range(1, len(values))]
        window = changes[-period:] if len(changes) >= period else changes
        gains = sum(change for change in window if change > 0)
        losses = abs(sum(change for change in window if change < 0))
        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100 - (100 / (1 + rs))

    def _macd(self, values: list[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> tuple[float, float, float]:
        if not values:
            return 0.0, 0.0, 0.0
        macd_series = []
        for index in range(len(values)):
            window = values[: index + 1]
            macd_series.append(self._ema(window, fast_period) - self._ema(window, slow_period))
        macd_line = macd_series[-1]
        signal_line = self._ema(macd_series, signal_period)
        return macd_line, signal_line, macd_line - signal_line

    def _bollinger_bands(self, values: list[float], period: int, std_multiplier: float) -> tuple[float, float, float]:
        if not values:
            return 0.0, 0.0, 0.0
        window = values[-period:] if len(values) >= period else values
        middle = sum(window) / len(window)
        variance = sum((value - middle) ** 2 for value in window) / len(window)
        std = math.sqrt(variance)
        return middle, middle + std_multiplier * std, middle - std_multiplier * std

    def _atr(self, highs: list[float], lows: list[float], closes: list[float], period: int) -> float:
        if not highs or not lows or not closes:
            return 0.0
        if len(closes) < 2:
            return highs[-1] - lows[-1]

        true_ranges = []
        for index in range(1, len(closes)):
            high = highs[index]
            low = lows[index]
            previous_close = closes[index - 1]
            true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))

        if not true_ranges:
            return 0.0
        window = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
        return sum(window) / len(window)
