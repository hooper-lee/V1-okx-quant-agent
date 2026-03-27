class BaseStrategy:
    name = "base"

    def generate_signal(self, indicators: dict) -> dict:
        return {"signal": "hold", "reason": "No strategy logic implemented.", "score": 0}


class SMACrossoverStrategy(BaseStrategy):
    name = "sma_crossover"

    def generate_signal(self, indicators: dict) -> dict:
        macd = indicators.get("macd", {})
        trend_score = 0
        reasons = []

        if indicators["sma_fast"] > indicators["sma_slow"]:
            trend_score += 1
            reasons.append("SMA 多头排列")
        if indicators["ema_fast"] > indicators["ema_slow"]:
            trend_score += 1
            reasons.append("EMA 多头排列")
        if macd.get("histogram", 0) > 0:
            trend_score += 1
            reasons.append("MACD 动能为正")
        if indicators["rsi"] < 68:
            trend_score += 1
            reasons.append("RSI 未过热")
        if indicators["last_close"] < indicators["bollinger_bands"]["upper"]:
            trend_score += 1
            reasons.append("价格未突破布林上轨")

        if trend_score >= 4:
            return {"signal": "buy", "reason": "、".join(reasons), "score": trend_score}

        sell_score = 0
        if indicators["sma_fast"] < indicators["sma_slow"]:
            sell_score += 1
        if indicators["ema_fast"] < indicators["ema_slow"]:
            sell_score += 1
        if macd.get("histogram", 0) < 0:
            sell_score += 1
        if indicators["rsi"] > 58:
            sell_score += 1
        if indicators["last_close"] >= indicators["bollinger_bands"]["upper"] * 0.995:
            sell_score += 1
        if sell_score >= 3:
            return {"signal": "sell", "reason": "趋势减弱且价格逼近高位，触发趋势减仓。", "score": -sell_score}

        return {"signal": "hold", "reason": "趋势指标尚未形成一致方向。", "score": trend_score}


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def generate_signal(self, indicators: dict) -> dict:
        boll = indicators.get("bollinger_bands", {})
        price = indicators.get("last_close", 0)
        volume_ma = indicators.get("volume_ma", 0)
        volume_ok = indicators.get("last_volume", 0) >= volume_ma * 0.8 if volume_ma else True

        if price <= boll.get("lower", 0) and indicators["rsi"] < 35 and volume_ok:
            return {"signal": "buy", "reason": "价格接近布林下轨，RSI 偏弱，满足均值回归入场。", "score": 3}
        if price >= boll.get("upper", 0) and indicators["rsi"] > 68:
            return {"signal": "sell", "reason": "价格接近布林上轨，RSI 偏热，满足均值回归离场。", "score": -3}
        return {"signal": "hold", "reason": "未达到布林带与 RSI 的极值区间。", "score": 0}


class NewsSentimentStrategy(BaseStrategy):
    name = "news_sentiment"

    def generate_signal(self, indicators: dict) -> dict:
        macd = indicators.get("macd", {})
        if indicators["ema_fast"] > indicators["ema_slow"] and macd.get("line", 0) > macd.get("signal", 0) and indicators["atr"] < indicators["last_close"] * 0.025:
            return {"signal": "buy", "reason": "趋势、动能与波动率组合支持顺势配置。", "score": 4}
        if (
            (indicators["ema_fast"] < indicators["ema_slow"] and macd.get("line", 0) < macd.get("signal", 0))
            or indicators["rsi"] > 64
            or indicators["last_close"] >= indicators["bollinger_bands"]["upper"] * 0.998
        ):
            return {"signal": "sell", "reason": "趋势动能走弱或价格逼近高位，新闻面策略倾向减仓。", "score": -4}
        return {"signal": "hold", "reason": "多因子信号尚未共振。", "score": 1}


class StrategyRegistry:
    def __init__(self, indicator_service) -> None:
        self.indicator_service = indicator_service
        self._strategies = {
            "sma_crossover": SMACrossoverStrategy(),
            "mean_reversion": MeanReversionStrategy(),
            "news_sentiment": NewsSentimentStrategy(),
        }
        self._type_defaults = {
            "trend": "sma_crossover",
            "reversal": "mean_reversion",
            "hybrid": "news_sentiment",
            "custom": "sma_crossover",
        }

    def get(self, name: str, strategy_type: str | None = None) -> BaseStrategy:
        if name in self._strategies:
            return self._strategies[name]
        if strategy_type:
            mapped = self._type_defaults.get(str(strategy_type).lower())
            if mapped and mapped in self._strategies:
                return self._strategies[mapped]
        return self._strategies["sma_crossover"]

    def list_names(self) -> list[str]:
        return list(self._strategies.keys())
