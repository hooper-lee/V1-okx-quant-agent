import math
from typing import Optional


class BacktestingEngine:
    def __init__(self, strategy_registry, indicator_service) -> None:
        self.strategy_registry = strategy_registry
        self.indicator_service = indicator_service

    def run(self, candles: list[dict], strategy_name: str, initial_capital: float, strategy_config: Optional[dict] = None) -> dict:
        strategy = self.strategy_registry.get(strategy_name)
        strategy_config = strategy_config or {}
        cash = initial_capital
        position = 0.0
        entry_price = 0.0
        trades = []
        equity_curve = []
        fees_paid = 0.0
        fee_rate = 0.001
        slippage_rate = 0.0005
        leverage = float(strategy_config.get("leverage", 1.0) or 1.0)
        entry_allocation_pct = float(strategy_config.get("entry_allocation_pct", 25.0) or 25.0)
        max_position_pct = float(strategy_config.get("max_position_pct", 50.0) or 50.0)
        max_drawdown_limit_pct = float(strategy_config.get("max_drawdown_limit_pct", 12.0) or 12.0)
        wins = 0
        losses = 0
        closed_trade_pnls = []
        halted = False
        halt_reason = ""

        for index in range(26, len(candles)):
            if halted:
                break
            window = candles[: index + 1]
            indicators = self.indicator_service.calculate(window)
            signal = strategy.generate_signal(indicators)
            market_price = float(candles[index]["close"])
            current_equity = cash + position * market_price
            max_position_notional = current_equity * (max_position_pct / 100)

            if signal["signal"] == "buy" and position == 0 and cash > market_price * 0.05:
                executed_price = market_price * (1 + slippage_rate)
                allocation = min(cash * (entry_allocation_pct / 100), max_position_notional / max(leverage, 1.0))
                leveraged_notional = allocation * leverage
                units = leveraged_notional / executed_price
                fee = leveraged_notional * fee_rate
                cash -= allocation + fee
                position = units
                entry_price = executed_price
                fees_paid += fee
                trades.append(
                    {
                        "side": "buy",
                        "units": round(units, 6),
                        "price": round(executed_price, 4),
                        "market_price": market_price,
                        "fee": round(fee, 4),
                        "allocation": round(allocation, 4),
                        "leverage": leverage,
                        "index": index,
                    }
                )
            elif signal["signal"] == "sell" and position > 0:
                executed_price = market_price * (1 - slippage_rate)
                notional = position * executed_price
                fee = notional * fee_rate
                pnl = position * (executed_price - entry_price) - fee
                cash += notional - fee
                position = 0.0
                fees_paid += fee
                closed_trade_pnls.append(pnl)
                if pnl >= 0:
                    wins += 1
                else:
                    losses += 1
                trades.append(
                    {
                        "side": "sell",
                        "units": round(notional / executed_price if executed_price else 0, 6),
                        "price": round(executed_price, 4),
                        "market_price": market_price,
                        "fee": round(fee, 4),
                        "pnl": round(pnl, 4),
                        "leverage": leverage,
                        "index": index,
                    }
                )

            equity = cash + position * market_price
            equity_curve.append({"index": index, "equity": round(equity, 4)})
            drawdown_pct = self._max_drawdown_pct(equity_curve)
            if max_drawdown_limit_pct > 0 and drawdown_pct >= max_drawdown_limit_pct:
                halted = True
                halt_reason = f"回测触发最大回撤限制 {max_drawdown_limit_pct:.2f}%"

        if position > 0:
            market_price = float(candles[-1]["close"])
            executed_price = market_price * (1 - slippage_rate)
            notional = position * executed_price
            fee = notional * fee_rate
            pnl = position * (executed_price - entry_price) - fee
            cash += notional - fee
            position = 0.0
            fees_paid += fee
            closed_trade_pnls.append(pnl)
            if pnl >= 0:
                wins += 1
            else:
                losses += 1
            trades.append(
                {
                    "side": "close",
                    "units": round(notional / executed_price if executed_price else 0, 6),
                    "price": round(executed_price, 4),
                    "market_price": market_price,
                    "fee": round(fee, 4),
                    "pnl": round(pnl, 4),
                    "leverage": leverage,
                    "index": len(candles) - 1,
                }
            )
            equity_curve.append({"index": len(candles) - 1, "equity": round(cash, 4)})

        final_equity = cash + position * candles[-1]["close"]
        pnl = final_equity - initial_capital
        total_return_pct = (pnl / initial_capital) * 100 if initial_capital else 0.0
        max_drawdown_pct = self._max_drawdown_pct(equity_curve)
        period_returns = self._period_returns(equity_curve)
        sharpe_ratio = self._sharpe_ratio(period_returns)
        trade_count = len([item for item in trades if item["side"] in {"sell", "close"}])
        win_rate_pct = (wins / trade_count * 100) if trade_count else 0.0
        avg_trade_pnl = (sum(closed_trade_pnls) / len(closed_trade_pnls)) if closed_trade_pnls else 0.0
        gross_profit = sum(value for value in closed_trade_pnls if value > 0)
        gross_loss = abs(sum(value for value in closed_trade_pnls if value < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss else (gross_profit if gross_profit else 0.0)

        return {
            "strategy_name": strategy_name,
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "pnl": round(pnl, 2),
            "total_return_pct": round(total_return_pct, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "fees_paid": round(fees_paid, 4),
            "trade_count": trade_count,
            "win_rate_pct": round(win_rate_pct, 2),
            "avg_trade_pnl": round(avg_trade_pnl, 4),
            "profit_factor": round(profit_factor, 4),
            "open_position": round(position, 4),
            "halted": halted,
            "halt_reason": halt_reason,
            "strategy_config": {
                "leverage": leverage,
                "entry_allocation_pct": entry_allocation_pct,
                "max_position_pct": max_position_pct,
                "max_drawdown_limit_pct": max_drawdown_limit_pct,
            },
            "equity_curve": equity_curve,
            "trades": trades,
        }

    def _max_drawdown_pct(self, equity_curve: list[dict]) -> float:
        peak = 0.0
        max_drawdown = 0.0
        for point in equity_curve:
            equity = float(point["equity"])
            peak = max(peak, equity)
            if peak > 0:
                drawdown = (peak - equity) / peak * 100
                max_drawdown = max(max_drawdown, drawdown)
        return max_drawdown

    def _period_returns(self, equity_curve: list[dict]) -> list[float]:
        if len(equity_curve) < 2:
            return []
        returns = []
        for index in range(1, len(equity_curve)):
            prev_equity = float(equity_curve[index - 1]["equity"])
            curr_equity = float(equity_curve[index]["equity"])
            if prev_equity > 0:
                returns.append((curr_equity - prev_equity) / prev_equity)
        return returns

    def _sharpe_ratio(self, period_returns: list[float]) -> float:
        if len(period_returns) < 2:
            return 0.0
        avg_return = sum(period_returns) / len(period_returns)
        variance = sum((value - avg_return) ** 2 for value in period_returns) / (len(period_returns) - 1)
        std = math.sqrt(variance)
        if std == 0:
            return 0.0
        return (avg_return / std) * math.sqrt(len(period_returns))
