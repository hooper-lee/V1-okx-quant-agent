from typing import Optional


class RiskControlService:
    def __init__(self, settings, trade_record_store) -> None:
        self.settings = settings
        self.trade_record_store = trade_record_store

    def validate_order(
        self,
        symbol: str,
        side: str,
        size: float,
        last_price: float,
        risk_limit_pct: Optional[float] = None,
        max_position_pct: Optional[float] = None,
        available_equity: Optional[float] = None,
        max_drawdown_limit_pct: Optional[float] = None,
    ) -> dict:
        notional = size * last_price
        effective_equity = float(available_equity or self.settings.max_order_notional or 0)
        risk_limit_pct = float(risk_limit_pct or self.settings.risk_per_trade * 100)
        max_position_pct = float(max_position_pct or 100)
        max_drawdown_limit_pct = float(max_drawdown_limit_pct or 100)
        if size <= 0:
            return {"approved": False, "reason": "Order size must be positive."}
        if notional > self.settings.max_order_notional:
            return {"approved": False, "reason": f"Order notional {notional:.2f} exceeds configured limit."}
        if effective_equity > 0 and risk_limit_pct > 0:
            max_risk_notional = effective_equity * (risk_limit_pct / 100)
            if notional > max_risk_notional:
                return {
                    "approved": False,
                    "reason": f"Order notional {notional:.2f} exceeds risk budget {max_risk_notional:.2f}.",
                }
        if effective_equity > 0 and max_position_pct > 0:
            max_position_notional = effective_equity * (max_position_pct / 100)
            if notional > max_position_notional:
                return {
                    "approved": False,
                    "reason": f"Order notional {notional:.2f} exceeds max position cap {max_position_notional:.2f}.",
                }
        recent_records = self.trade_record_store.list_all()[-20:]
        if max_drawdown_limit_pct < 100 and recent_records:
            realized_pnl = 0.0
            for item in recent_records:
                execution = item.get("execution", {})
                realized_pnl += float(execution.get("realized_pnl", 0) or 0)
            if effective_equity > 0:
                realized_drawdown_pct = abs(min(realized_pnl, 0)) / effective_equity * 100
                if realized_drawdown_pct >= max_drawdown_limit_pct:
                    return {
                        "approved": False,
                        "reason": f"Recent realized drawdown {realized_drawdown_pct:.2f}% exceeds strategy limit {max_drawdown_limit_pct:.2f}%.",
                    }
        return {
            "approved": True,
            "reason": "approved",
            "symbol": symbol,
            "side": side,
            "notional": round(notional, 2),
            "risk_limit_pct": round(risk_limit_pct, 2),
            "max_position_pct": round(max_position_pct, 2),
        }
