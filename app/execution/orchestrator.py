from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class TradingOrchestrator:
    def __init__(self, market_data_service, quant_engine, risk_control_service, executor, trade_record_store, learning_service=None) -> None:
        self.market_data_service = market_data_service
        self.quant_engine = quant_engine
        self.risk_control_service = risk_control_service
        self.executor = executor
        self.trade_record_store = trade_record_store
        self.learning_service = learning_service

    def execute_trade(self, symbol: str, side: str, size: float, strategy_name: str, strategy_config: Optional[dict] = None) -> dict:
        strategy_config = strategy_config or {}
        timeframe = strategy_config.get("timeframe", "1h")
        candles = self.market_data_service.get_candles(symbol=symbol, timeframe=timeframe, limit=50)
        analysis = self.quant_engine.analyze_market(
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=strategy_name,
            strategy_config=strategy_config,
            candles=candles,
        )
        target_capital = float(strategy_config.get("target_capital", 10000) or 10000)
        risk_check = self.risk_control_service.validate_order(
            symbol=symbol,
            side=side,
            size=size,
            last_price=candles[-1]["close"],
            risk_limit_pct=strategy_config.get("risk_limit_pct"),
            max_position_pct=strategy_config.get("max_position_pct"),
            available_equity=target_capital,
            max_drawdown_limit_pct=strategy_config.get("max_drawdown_limit_pct"),
        )

        if not risk_check["approved"]:
            return {
                "status": "blocked",
                "reason": risk_check["reason"],
                "analysis": analysis,
            }

        execution = self.executor.place_order(symbol=symbol, side=side, size=size, strategy_config=strategy_config)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "size": size,
            "strategy_name": strategy_name,
            "analysis": analysis,
            "execution": execution,
        }
        self.trade_record_store.save(record)
        if self.learning_service is not None:
            try:
                self.learning_service.store_trade_review(record)
            except Exception:
                pass
        return {"status": "success", "analysis": analysis, "execution": execution}
