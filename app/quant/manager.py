from __future__ import annotations
from typing import Optional


class QuantEngine:
    def __init__(
        self,
        market_data_service,
        strategy_registry,
        indicator_service,
        backtesting_engine,
        risk_control_service,
        agent_decision_service,
        rl_service,
    ) -> None:
        self.market_data_service = market_data_service
        self.strategy_registry = strategy_registry
        self.indicator_service = indicator_service
        self.backtesting_engine = backtesting_engine
        self.risk_control_service = risk_control_service
        self.agent_decision_service = agent_decision_service
        self.rl_service = rl_service

    def analyze_market(
        self,
        symbol: str,
        timeframe: str,
        strategy_name: str,
        strategy_config: Optional[dict] = None,
        candles: Optional[list[dict]] = None,
    ) -> dict:
        candles = candles or self.market_data_service.get_candles(symbol=symbol, timeframe=timeframe, limit=50)
        indicators = self.indicator_service.calculate(candles)
        strategy_type = (strategy_config or {}).get("strategy_type")
        strategy = self.strategy_registry.get(strategy_name, strategy_type=strategy_type)
        signal = strategy.generate_signal(indicators)
        agent_output = self.agent_decision_service.decide(symbol=symbol, indicators=indicators, signal=signal)
        rl_hint = self.rl_service.recommend(state=indicators)
        strategy_config = strategy_config or {}
        target_capital = float(strategy_config.get("target_capital", 10000) or 10000)
        leverage = float(strategy_config.get("leverage", 1.0) or 1.0)
        entry_allocation_pct = float(strategy_config.get("entry_allocation_pct", 25.0) or 25.0)
        max_position_pct = float(strategy_config.get("max_position_pct", 50.0) or 50.0)
        risk_limit_pct = float(strategy_config.get("risk_limit_pct", 2.0) or 2.0)
        max_drawdown_limit_pct = float(strategy_config.get("max_drawdown_limit_pct", 12.0) or 12.0)
        last_price = float(candles[-1]["close"])
        preview_notional = target_capital * (entry_allocation_pct / 100.0) * leverage
        preview_cap = target_capital * (max_position_pct / 100.0)
        preview_size = min(preview_notional, preview_cap) / max(last_price, 1.0)
        agent_output = {**agent_output}
        if agent_output.get("action") in {"buy", "sell"} and not agent_output.get("position_size"):
            agent_output["position_size"] = round(max(preview_size, 0.0), 6)
        agent_output["symbol"] = str(agent_output.get("symbol") or symbol)
        agent_output["structured"] = {
            "market_view": agent_output.get("market_view", "sideways neutral"),
            "confidence": float(agent_output.get("confidence", 0.5)),
            "action": agent_output.get("action", agent_output.get("decision", "hold")),
            "symbol": agent_output["symbol"],
            "position_size": agent_output.get("position_size"),
            "reason": agent_output.get("reason") or [agent_output.get("rationale", "No rationale provided.")],
        }
        risk_preview = self.risk_control_service.validate_order(
            symbol=symbol,
            side=signal["signal"] if signal["signal"] != "hold" else "buy",
            size=max(round(preview_size, 6), 0.0001),
            last_price=last_price,
            risk_limit_pct=risk_limit_pct,
            max_position_pct=max_position_pct,
            available_equity=target_capital,
            max_drawdown_limit_pct=max_drawdown_limit_pct,
        )
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy_name": strategy_name,
            "last_price": last_price,
            "indicators": indicators,
            "signal": signal,
            "agent": agent_output,
            "risk_preview": risk_preview,
            "rl_hint": rl_hint,
            "positioning": {
                "target_capital": target_capital,
                "leverage": leverage,
                "entry_allocation_pct": entry_allocation_pct,
                "max_position_pct": max_position_pct,
                "max_drawdown_limit_pct": max_drawdown_limit_pct,
                "preview_notional": round(min(preview_notional, preview_cap), 2),
                "preview_size": round(max(preview_size, 0.0), 6),
            },
        }

    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy_name: str,
        initial_capital: float,
        bars: int,
        strategy_config: Optional[dict] = None,
    ) -> dict:
        candles = self.market_data_service.get_candles(symbol=symbol, timeframe=timeframe, limit=bars)
        result = self.backtesting_engine.run(
            candles=candles,
            strategy_name=strategy_name,
            initial_capital=initial_capital,
            strategy_config=strategy_config or {},
        )
        return {"symbol": symbol, "timeframe": timeframe, **result}
