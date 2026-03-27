from __future__ import annotations

import json
from datetime import datetime


class LearningService:
    def __init__(self, memory_service, runtime, prompt_template_service) -> None:
        self.memory_service = memory_service
        self.runtime = runtime
        self.prompt_template_service = prompt_template_service

    def store_backtest_summary(self, item: dict) -> dict:
        topic = f"backtest:{item.get('strategy_name', 'unknown')}:{item.get('run_id', datetime.now().strftime('%Y%m%d%H%M%S'))}"
        content = (
            f"Backtest {item.get('label', '')}\n"
            f"strategy={item.get('strategy_name')}\n"
            f"symbol={item.get('symbol')}\n"
            f"timeframe={item.get('timeframe')}\n"
            f"initial_capital={item.get('initial_capital')}\n"
            f"total_return_pct={item.get('total_return_pct')}\n"
            f"max_drawdown_pct={item.get('max_drawdown_pct')}\n"
            f"sharpe_ratio={item.get('sharpe_ratio')}\n"
            f"trade_count={item.get('trade_count')}\n"
            f"win_rate_pct={item.get('win_rate_pct')}\n"
            f"profit_factor={item.get('profit_factor')}\n"
        )
        self.memory_service.write(topic=topic, content=content)
        return {"topic": topic, "content": content}

    def store_trade_review(self, record: dict) -> dict:
        execution = record.get("execution", {})
        analysis = record.get("analysis", {})
        topic = f"trade:{record.get('strategy_name', 'unknown')}:{record.get('timestamp', datetime.now().isoformat())}"
        content = (
            f"Trade review\n"
            f"strategy={record.get('strategy_name')}\n"
            f"symbol={record.get('symbol')}\n"
            f"side={record.get('side')}\n"
            f"size={record.get('size')}\n"
            f"signal={analysis.get('signal', {}).get('signal')}\n"
            f"agent_decision={analysis.get('agent', {}).get('decision')}\n"
            f"agent_confidence={analysis.get('agent', {}).get('confidence')}\n"
            f"execution_status={execution.get('status')}\n"
            f"instrument_type={execution.get('instrument_type')}\n"
            f"risk_reason={analysis.get('risk_preview', {}).get('reason')}\n"
        )
        self.memory_service.write(topic=topic, content=content)
        return {"topic": topic, "content": content}

    def store_daily_summary(
        self,
        date_label: str,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        report: dict,
        analysis: dict,
        account_metrics: dict,
        backtests: list[dict],
        trades: list[dict],
    ) -> dict:
        payload = {
            "date": date_label,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "daily_report": report,
            "analysis": {
                "signal": analysis.get("signal", {}),
                "agent": analysis.get("agent", {}),
                "risk_preview": analysis.get("risk_preview", {}),
                "last_price": analysis.get("last_price"),
            },
            "account_metrics": {
                "total_asset": account_metrics.get("total_asset"),
                "available_asset": account_metrics.get("available_asset"),
                "yield_rate": account_metrics.get("yield_rate"),
                "target_capital": account_metrics.get("target_capital"),
            },
            "recent_backtests": backtests[:3],
            "recent_trades": trades[:5],
        }
        structured_summary = self.runtime.invoke_json(
            system_prompt=(
                f"{self.prompt_template_service.render('daily_reflection')}\n"
                "请输出 JSON，不要输出 markdown。"
                "字段包含：date,strategy_name,market_view,confidence,action,symbol,position_size,reason,risk_note,next_step,summary。"
                "reason 必须是字符串数组。confidence 取 0 到 1。"
            ),
            user_prompt=json.dumps(payload, ensure_ascii=False),
        )
        if not structured_summary:
            structured_summary = self._build_fallback_daily_summary(payload)
        content = json.dumps(structured_summary, ensure_ascii=False, indent=2)
        topic = f"daily-summary:{strategy_name}:{date_label}"
        self.memory_service.write(topic=topic, content=content)
        return {"topic": topic, "content": content, "structured": structured_summary}

    def list_daily_summaries(self, strategy_name: str = "", limit: int = 10) -> list[dict]:
        prefix = f"daily-summary:{strategy_name}:" if strategy_name else "daily-summary:"
        items = self.memory_service.list_by_topic_prefix(prefix=prefix, limit=limit)
        parsed: list[dict] = []
        for item in items:
            topic = str(item.get("topic", ""))
            _, stored_strategy_name, date_label = (topic.split(":", 2) + ["", "", ""])[:3]
            raw_content = item.get("content", "")
            structured = None
            content_text = str(raw_content or "")
            try:
                structured = json.loads(content_text)
                if isinstance(structured, dict):
                    content_text = str(
                        structured.get("summary")
                        or structured.get("next_step")
                        or structured.get("risk_note")
                        or content_text
                    )
                else:
                    structured = None
            except (TypeError, ValueError, json.JSONDecodeError):
                structured = None
            parsed.append(
                {
                    "topic": topic,
                    "strategy_name": stored_strategy_name or strategy_name,
                    "date": date_label,
                    "content": content_text,
                    "raw_content": raw_content,
                    "structured": structured,
                    "created_at": item.get("created_at", ""),
                }
            )
        return parsed

    def suggest_strategy_update(
        self,
        strategy: dict,
        summary: str,
        analysis: dict,
        account_metrics: dict,
        backtests: list[dict],
        trades: list[dict],
    ) -> dict | None:
        config = strategy.get("config", {})
        payload = {
            "strategy_name": strategy.get("name"),
            "strategy_type": strategy.get("type"),
            "risk_preference": strategy.get("risk_preference"),
            "description": strategy.get("description"),
            "execution_notes": strategy.get("execution_notes"),
            "config": config,
            "analysis": {
                "signal": analysis.get("signal", {}),
                "agent": analysis.get("agent", {}),
                "risk_preview": analysis.get("risk_preview", {}),
                "last_price": analysis.get("last_price"),
                "symbol": analysis.get("symbol"),
                "timeframe": analysis.get("timeframe"),
            },
            "account_metrics": {
                "total_asset": account_metrics.get("total_asset"),
                "available_asset": account_metrics.get("available_asset"),
                "yield_rate": account_metrics.get("yield_rate"),
                "target_capital": account_metrics.get("target_capital"),
            },
            "recent_backtests": backtests[:3],
            "recent_trades": trades[:5],
            "daily_summary": summary,
        }
        suggestion = self.runtime.invoke_json(
            system_prompt=(
                "你是量化策略调参助手。"
                "请根据输入的日总结、当前策略和最近执行结果，输出一个 JSON 对象。"
                "仅在确实有必要时才建议调整。"
                "允许的字段有：strategy_type,risk_preference,description,execution_notes,timeframe,"
                "target_capital,target_horizon_days,leverage,entry_allocation_pct,max_position_pct,"
                "max_drawdown_limit_pct,margin_mode,fast_period,slow_period,rsi_period,"
                "take_profit_pct,stop_loss_pct,risk_limit_pct。"
                "不要返回 name，不要解释，只返回 JSON。"
            ),
            user_prompt=json.dumps(payload, ensure_ascii=False),
        )
        if suggestion is None:
            return None

        current = {
            "strategy_type": strategy.get("type", "custom"),
            "risk_preference": strategy.get("risk_preference", "balanced"),
            "description": strategy.get("description") or "用户创建的自定义策略。",
            "execution_notes": strategy.get("execution_notes") or "按策略信号与风控结果执行。",
            "symbol": config.get("symbol", "BTC-USDT-SWAP"),
            "timeframe": config.get("timeframe", "1h"),
            "target_capital": float(config.get("target_capital", 10000) or 10000),
            "target_horizon_days": int(config.get("target_horizon_days", 30) or 30),
            "leverage": float(config.get("leverage", 1.0) or 1.0),
            "entry_allocation_pct": float(config.get("entry_allocation_pct", 25) or 25),
            "max_position_pct": float(config.get("max_position_pct", 50) or 50),
            "max_drawdown_limit_pct": float(config.get("max_drawdown_limit_pct", 12) or 12),
            "margin_mode": config.get("margin_mode", "cross"),
            "fast_period": int(config.get("fast_period", 7) or 7),
            "slow_period": int(config.get("slow_period", 20) or 20),
            "rsi_period": int(config.get("rsi_period", 14) or 14),
            "take_profit_pct": float(config.get("take_profit_pct", 8) or 8),
            "stop_loss_pct": float(config.get("stop_loss_pct", 3) or 3),
            "risk_limit_pct": float(config.get("risk_limit_pct", 2) or 2),
        }

        def clamp_number(value, fallback, minimum=None, maximum=None, cast=float):
            try:
                parsed = cast(value)
            except (TypeError, ValueError):
                parsed = fallback
            if minimum is not None:
                parsed = max(minimum, parsed)
            if maximum is not None:
                parsed = min(maximum, parsed)
            return parsed

        normalized = {
            "strategy_type": str(suggestion.get("strategy_type") or current["strategy_type"]),
            "risk_preference": str(suggestion.get("risk_preference") or current["risk_preference"]),
            "description": str(suggestion.get("description") or current["description"]),
            "execution_notes": str(suggestion.get("execution_notes") or current["execution_notes"]),
            "config": {
                "symbol": current["symbol"],
                "timeframe": str(suggestion.get("timeframe") or current["timeframe"]),
                "target_capital": clamp_number(suggestion.get("target_capital"), current["target_capital"], 1, 1_000_000_000),
                "target_horizon_days": clamp_number(suggestion.get("target_horizon_days"), current["target_horizon_days"], 1, 3650, int),
                "leverage": clamp_number(suggestion.get("leverage"), current["leverage"], 1.0, 50.0),
                "entry_allocation_pct": clamp_number(suggestion.get("entry_allocation_pct"), current["entry_allocation_pct"], 1.0, 100.0),
                "max_position_pct": clamp_number(suggestion.get("max_position_pct"), current["max_position_pct"], 1.0, 100.0),
                "max_drawdown_limit_pct": clamp_number(suggestion.get("max_drawdown_limit_pct"), current["max_drawdown_limit_pct"], 1.0, 100.0),
                "margin_mode": str(suggestion.get("margin_mode") or current["margin_mode"]),
                "fast_period": clamp_number(suggestion.get("fast_period"), current["fast_period"], 2, 100, int),
                "slow_period": clamp_number(suggestion.get("slow_period"), current["slow_period"], 3, 300, int),
                "rsi_period": clamp_number(suggestion.get("rsi_period"), current["rsi_period"], 2, 100, int),
                "take_profit_pct": clamp_number(suggestion.get("take_profit_pct"), current["take_profit_pct"], 0.1, 100.0),
                "stop_loss_pct": clamp_number(suggestion.get("stop_loss_pct"), current["stop_loss_pct"], 0.1, 100.0),
                "risk_limit_pct": clamp_number(suggestion.get("risk_limit_pct"), current["risk_limit_pct"], 0.1, 100.0),
            },
        }
        applied_fields: list[str] = []
        for field in ("strategy_type", "risk_preference", "description", "execution_notes"):
            if normalized[field] != current[field]:
                applied_fields.append(field)
        for field, value in normalized["config"].items():
            if value != current[field]:
                applied_fields.append(field)
        return {"payload": normalized, "applied_fields": applied_fields}

    def _build_fallback_daily_summary(self, payload: dict) -> dict:
        analysis = payload["analysis"]
        account = payload["account_metrics"]
        agent = analysis.get("agent", {})
        reasons = agent.get("reason")
        if not isinstance(reasons, list) or not reasons:
            rationale = agent.get("rationale") or "暂无额外原因"
            reasons = [str(rationale)]
        return {
            "date": payload["date"],
            "strategy_name": payload["strategy_name"],
            "market_view": agent.get("market_view", "sideways neutral"),
            "confidence": float(agent.get("confidence", 0) or 0),
            "action": agent.get("action") or agent.get("decision", "hold"),
            "symbol": payload["symbol"],
            "position_size": agent.get("position_size"),
            "reason": [str(item) for item in reasons if str(item).strip()],
            "risk_note": str(analysis.get("risk_preview", {}).get("reason", "无")),
            "next_step": "结合账户表现和风险提醒，决定是否保持当前策略或继续观察。",
            "summary": (
                f"{payload['date']} {payload['strategy_name']} 日总结。"
                f"当前信号 {analysis.get('signal', {}).get('signal', 'hold')}，"
                f"Agent 决策 {agent.get('action') or agent.get('decision', 'hold')}，"
                f"置信度 {agent.get('confidence', 0)}。"
                f"账户总资产 {account.get('total_asset')}，收益率 {account.get('yield_rate')}%。"
            ),
        }
