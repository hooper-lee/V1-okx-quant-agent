from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable


class AutomationService:
    def __init__(
        self,
        runtime_config_service,
        strategy_store,
        trading_orchestrator,
        backtest_store,
        trade_record_store,
        learning_service,
        notification_service,
        snapshot_builder: Callable[..., dict],
    ) -> None:
        self.runtime_config_service = runtime_config_service
        self.strategy_store = strategy_store
        self.trading_orchestrator = trading_orchestrator
        self.backtest_store = backtest_store
        self.trade_record_store = trade_record_store
        self.learning_service = learning_service
        self.notification_service = notification_service
        self.snapshot_builder = snapshot_builder
        self._task: asyncio.Task | None = None
        self._last_auto_trade_run_at = ""
        self._last_daily_summary_run_at = ""
        self._last_auto_trade_results: list[dict] = []
        self._last_daily_summary_results: list[dict] = []

    def default_config(self) -> dict:
        return {
            "auto_trade_enabled": False,
            "auto_trade_interval_minutes": 15,
            "auto_trade_strategy_names": [],
            "auto_trade_min_confidence": 0.55,
            "daily_summary_enabled": False,
            "daily_summary_hour": 21,
            "daily_summary_strategy_names": [],
            "daily_summary_apply_ai_updates": False,
            "daily_summary_last_run_date": "",
        }

    def config(self) -> dict:
        current = self.default_config()
        current.update(self.runtime_config_service.get("automation_config", {}) or {})
        return current

    def update_config(self, payload: dict) -> dict:
        current = self.config()
        current.update({key: value for key, value in payload.items() if value is not None})
        self.runtime_config_service.save({"automation_config": current})
        return current

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._runner(), name="automation-service")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def status(self) -> dict:
        config = self.config()
        return {
            "service_running": bool(self._task and not self._task.done()),
            "config": config,
            "auto_trade": {
                "enabled": config["auto_trade_enabled"],
                "last_run_at": self._last_auto_trade_run_at,
                "results": self._last_auto_trade_results,
            },
            "daily_summary": {
                "enabled": config["daily_summary_enabled"],
                "last_run_at": self._last_daily_summary_run_at,
                "results": self._last_daily_summary_results,
            },
        }

    async def run_auto_trade_once(self) -> dict:
        config = self.config()
        strategy_names = config.get("auto_trade_strategy_names") or [item["name"] for item in self.strategy_store.list_all()]
        min_confidence = float(config.get("auto_trade_min_confidence", 0.55) or 0.55)
        results: list[dict] = []
        for strategy_name in strategy_names:
            strategy = self.strategy_store.get(strategy_name)
            if not strategy:
                results.append({"strategy_name": strategy_name, "status": "skipped", "reason": "strategy_not_found"})
                continue
            snapshot = self.snapshot_builder(strategy_name=strategy_name)
            analysis = snapshot["analysis"]
            decision = analysis.get("agent", {}).get("decision") or analysis.get("signal", {}).get("signal") or "hold"
            confidence = float(analysis.get("agent", {}).get("confidence", 0) or 0)
            if decision not in {"buy", "sell"}:
                results.append({"strategy_name": strategy_name, "status": "skipped", "reason": f"decision_{decision}"})
                continue
            if confidence < min_confidence:
                results.append(
                    {
                        "strategy_name": strategy_name,
                        "status": "skipped",
                        "reason": f"confidence_{confidence:.2f}_below_{min_confidence:.2f}",
                    }
                )
                continue
            size = float(analysis.get("positioning", {}).get("preview_size", 0) or 0)
            if size <= 0:
                results.append({"strategy_name": strategy_name, "status": "skipped", "reason": "invalid_size"})
                continue
            execution = self.trading_orchestrator.execute_trade(
                symbol=analysis["symbol"],
                side=decision,
                size=size,
                strategy_name=strategy_name,
                strategy_config=strategy.get("config", {}),
            )
            results.append(
                {
                    "strategy_name": strategy_name,
                    "symbol": analysis["symbol"],
                    "side": decision,
                    "size": size,
                    "status": execution.get("status", "unknown"),
                    "confidence": confidence,
                }
            )
        self._last_auto_trade_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._last_auto_trade_results = results
        return {"run_at": self._last_auto_trade_run_at, "results": results}

    async def run_daily_summary_once(self, force: bool = False) -> dict:
        config = self.config()
        today = datetime.now().strftime("%Y-%m-%d")
        if not force and config.get("daily_summary_last_run_date") == today:
            return {
                "run_at": self._last_daily_summary_run_at,
                "results": self._last_daily_summary_results,
                "skipped": True,
                "reason": "already_ran_today",
            }
        strategy_names = config.get("daily_summary_strategy_names") or [item["name"] for item in self.strategy_store.list_all()]
        apply_ai_updates = bool(config.get("daily_summary_apply_ai_updates"))
        results: list[dict] = []
        recent_backtests = self.backtest_store.list_all()
        recent_trades = self.trade_record_store.list_all()
        for strategy_name in strategy_names:
            strategy = self.strategy_store.get(strategy_name)
            if not strategy:
                results.append({"strategy_name": strategy_name, "status": "skipped", "reason": "strategy_not_found"})
                continue
            snapshot = self.snapshot_builder(strategy_name=strategy_name)
            memory_item = self.learning_service.store_daily_summary(
                date_label=today,
                strategy_name=strategy_name,
                symbol=snapshot["analysis"]["symbol"],
                timeframe=snapshot["analysis"]["timeframe"],
                report=snapshot["daily_report"],
                analysis=snapshot["analysis"],
                account_metrics=snapshot["account_metrics"],
                backtests=[item for item in recent_backtests if item.get("strategy_name") == strategy_name],
                trades=[item for item in recent_trades if item.get("strategy_name") == strategy_name],
            )
            result_item = {"strategy_name": strategy_name, "status": "stored", "topic": memory_item["topic"]}
            notification_result = self.notification_service.send_daily_summary(
                strategy_name=strategy_name,
                report=snapshot["daily_report"],
                summary=memory_item.get("structured") if isinstance(memory_item, dict) else None,
            )
            result_item["feishu"] = notification_result
            if apply_ai_updates:
                suggestion = self.learning_service.suggest_strategy_update(
                    strategy=strategy,
                    summary=memory_item.get("content", ""),
                    analysis=snapshot["analysis"],
                    account_metrics=snapshot["account_metrics"],
                    backtests=[item for item in recent_backtests if item.get("strategy_name") == strategy_name],
                    trades=[item for item in recent_trades if item.get("strategy_name") == strategy_name],
                )
                if suggestion and suggestion.get("payload"):
                    updated_item = self.strategy_store.update(strategy_name, suggestion["payload"])
                    if updated_item is not None:
                        result_item["ai_updated"] = True
                        result_item["applied_fields"] = suggestion.get("applied_fields", [])
                    else:
                        result_item["ai_updated"] = False
                        result_item["ai_update_reason"] = "strategy_not_found"
                else:
                    result_item["ai_updated"] = False
                    result_item["ai_update_reason"] = "no_suggestion"
            results.append(result_item)
        self._last_daily_summary_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._last_daily_summary_results = results
        config["daily_summary_last_run_date"] = today
        self.runtime_config_service.save({"automation_config": config})
        return {"run_at": self._last_daily_summary_run_at, "results": results}

    async def _runner(self) -> None:
        while True:
            config = self.config()
            now = datetime.now()
            if config.get("auto_trade_enabled"):
                due = True
                if self._last_auto_trade_run_at:
                    last_run = datetime.strptime(self._last_auto_trade_run_at, "%Y-%m-%d %H:%M:%S")
                    delta_seconds = (now - last_run).total_seconds()
                    due = delta_seconds >= int(config.get("auto_trade_interval_minutes", 15)) * 60
                if due:
                    try:
                        await self.run_auto_trade_once()
                    except Exception as exc:
                        self._last_auto_trade_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self._last_auto_trade_results = [{"status": "failed", "reason": str(exc)}]

            if config.get("daily_summary_enabled") and now.hour == int(config.get("daily_summary_hour", 21)):
                try:
                    await self.run_daily_summary_once(force=False)
                except Exception as exc:
                    self._last_daily_summary_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self._last_daily_summary_results = [{"status": "failed", "reason": str(exc)}]

            await asyncio.sleep(30)
