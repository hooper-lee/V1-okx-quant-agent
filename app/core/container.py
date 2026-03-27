from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import RUNTIME_CONFIG_PATH, STRATEGY_STORE_PATH, settings
from app.integrations.langchain_runtime import LangChainRuntime
from app.data.news_store import NewsRAGService
from app.data.backtest_store import BacktestStore
from app.data.record_store import TradeRecordStore
from app.data.strategy_store import StrategyStore
from app.data.vector_store import ExperienceVectorStore
from app.data.market_data import MarketDataService
from app.execution.okx_executor import OKXExecutor
from app.execution.orchestrator import TradingOrchestrator
from app.langchain_layer.agent_service import AgentDecisionService
from app.langchain_layer.chains import AnalysisChainService
from app.langchain_layer.memory_service import MemoryService
from app.langchain_layer.rag_service import RAGCoordinator
from app.quant.backtesting import BacktestingEngine
from app.quant.indicators import TechnicalIndicatorService
from app.quant.manager import QuantEngine
from app.quant.risk import RiskControlService
from app.quant.rl import ReinforcementLearningService
from app.quant.strategies import StrategyRegistry
from app.services.prompt_service import PromptTemplateService
from app.services.runtime_config_service import RuntimeConfigService
from app.services.learning_service import LearningService
from app.services.automation_service import AutomationService
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService

runtime_config_service = RuntimeConfigService(config_path=RUNTIME_CONFIG_PATH)
notification_service = NotificationService(runtime_config_service=runtime_config_service)
langchain_runtime = LangChainRuntime(settings=settings, runtime_config_service=runtime_config_service)
prompt_template_service = PromptTemplateService(base_dir=Path(__file__).resolve().parent.parent.parent / "prompts")
market_data_service = MarketDataService(settings=settings, runtime_config_service=runtime_config_service)
news_rag_service = NewsRAGService(runtime_config_service=runtime_config_service)
trade_record_store = TradeRecordStore()
backtest_store = BacktestStore()
experience_vector_store = ExperienceVectorStore(settings=settings, runtime=langchain_runtime)
strategy_store = StrategyStore(store_path=STRATEGY_STORE_PATH)
okx_client = market_data_service.okx_client

analysis_chain_service = AnalysisChainService(runtime=langchain_runtime, prompt_template_service=prompt_template_service)
memory_service = MemoryService(experience_store=experience_vector_store)
learning_service = LearningService(
    memory_service=memory_service,
    runtime=langchain_runtime,
    prompt_template_service=prompt_template_service,
)
rag_coordinator = RAGCoordinator(news_service=news_rag_service, experience_store=experience_vector_store)
agent_decision_service = AgentDecisionService(
    chain_service=analysis_chain_service,
    rag_service=rag_coordinator,
    memory_service=memory_service,
    runtime=langchain_runtime,
    prompt_template_service=prompt_template_service,
)

indicator_service = TechnicalIndicatorService()
strategy_registry = StrategyRegistry(indicator_service=indicator_service)
backtesting_engine = BacktestingEngine(strategy_registry=strategy_registry, indicator_service=indicator_service)
risk_control_service = RiskControlService(settings=settings, trade_record_store=trade_record_store)
rl_service = ReinforcementLearningService()
okx_executor = OKXExecutor(settings=settings, runtime_config_service=runtime_config_service)

quant_engine = QuantEngine(
    market_data_service=market_data_service,
    strategy_registry=strategy_registry,
    indicator_service=indicator_service,
    backtesting_engine=backtesting_engine,
    risk_control_service=risk_control_service,
    agent_decision_service=agent_decision_service,
    rl_service=rl_service,
)

trading_orchestrator = TradingOrchestrator(
    market_data_service=market_data_service,
    quant_engine=quant_engine,
    risk_control_service=risk_control_service,
    executor=okx_executor,
    trade_record_store=trade_record_store,
    learning_service=learning_service,
)



def build_system_overview() -> dict:
    return {
        "app": settings.app_name,
        "layers": {
            "frontend": ["dashboard", "market-monitor", "strategy-panel"],
            "backend_api": ["system", "market", "strategy", "backtest", "trade"],
            "langchain_core": ["chains", "rag", "agent", "memory"],
            "quant_engine": [
                "technical_indicators",
                "strategy_manager",
                "backtesting",
                "risk_control",
                "reinforcement_learning",
            ],
            "data_layer": ["market_data", "news_data", "trade_records", "vector_experience"],
            "execution_layer": ["okx_adapter", "risk_interceptor"],
        },
        "runtime": {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "vector_store": settings.chroma_persist_directory,
            "okx_mode": "paper" if settings.okx_use_paper else "live",
            "live_services_enabled": settings.use_live_services,
        },
    }


def build_dashboard_snapshot(strategy_name: Optional[str] = None) -> dict:
    strategy_items = strategy_store.list_all()
    current_strategy = strategy_store.get(strategy_name or "sma_crossover") or strategy_items[0]
    symbol = current_strategy.get("config", {}).get("symbol", settings.default_symbol)
    timeframe = current_strategy.get("config", {}).get("timeframe", "1h")
    analysis_strategy_config = {
        **current_strategy.get("config", {}),
        "strategy_type": current_strategy.get("type", "custom"),
    }
    candles = market_data_service.get_candles(symbol=symbol, timeframe=timeframe, limit=20)
    analysis = quant_engine.analyze_market(
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=current_strategy["name"],
        strategy_config=analysis_strategy_config,
        candles=candles,
    )
    last_price = candles[-1]["close"]
    progress = max(10, round(analysis["agent"]["confidence"] * 100))
    sources = build_news_sources_view(symbol=symbol, force_llm_summary=False)
    account_overview = okx_executor.get_account_overview()
    total_asset = float(account_overview.get("total_equity", 0) or 0)
    available_asset = float(account_overview.get("available_equity", 0) or 0)
    target_capital = float(current_strategy["config"].get("target_capital", 10000) or 10000)
    account_metrics = {
        "progress": progress,
        "total_asset": total_asset,
        "available_asset": available_asset,
        "target_capital": target_capital,
        "coin_asset": f"{symbol} / {current_strategy['type']} / {current_strategy['config'].get('target_horizon_days', 30)}天",
        "yield_rate": round(((total_asset - target_capital) / target_capital) * 100, 2) if target_capital else 0.0,
        "positions": [
            {
                "asset": item.get("asset", ""),
                "balance": float(item.get("equity", item.get("balance", 0)) or 0),
                "available": float(item.get("available", 0) or 0),
            }
            for item in account_overview.get("assets", [])
        ],
        "trend": [
            {"label": "D1", "value": last_price - 240},
            {"label": "D2", "value": last_price - 120},
            {"label": "D3", "value": last_price - 160},
            {"label": "D4", "value": last_price - 40},
            {"label": "D5", "value": last_price + 50},
            {"label": "D6", "value": last_price + 20},
            {"label": "D7", "value": last_price},
        ],
        "candles": candles,
        "account_overview": account_overview,
    }
    daily_report = analysis_chain_service.generate_daily_report(
        symbol=symbol,
        analysis=analysis,
        account_metrics=account_metrics,
        news_context=[item for source in sources for item in source["items"]],
    )

    return {
        "current_strategy": {
            "name": current_strategy["name"],
            "created_at": current_strategy["created_at"],
            "summary_items": [
                f"交易对：{symbol}",
                f"策略类型：{current_strategy['type']}",
                f"风险偏好：{current_strategy.get('risk_preference', 'balanced')}",
                f"周期：{current_strategy['config']['timeframe']}",
                f"目标资金 / 周期：{current_strategy['config'].get('target_capital', 10000)} / {current_strategy['config'].get('target_horizon_days', 30)}天",
                f"杠杆 / 保证金模式：{current_strategy['config'].get('leverage', 1.0)}x / {current_strategy['config'].get('margin_mode', 'cross')}",
                f"单次开仓 / 仓位上限：{current_strategy['config'].get('entry_allocation_pct', 25)}% / {current_strategy['config'].get('max_position_pct', 50)}%",
                f"最大回撤限制：{current_strategy['config'].get('max_drawdown_limit_pct', 12)}%",
                f"执行说明：{current_strategy.get('execution_notes', '按策略信号与风控结果执行。')}",
                f"均线参数：{current_strategy['config']['fast_period']}/{current_strategy['config']['slow_period']}",
                f"EMA：{analysis['indicators']['ema_fast']:.2f} / {analysis['indicators']['ema_slow']:.2f}",
                f"MACD：{analysis['indicators']['macd']['line']:.2f} / {analysis['indicators']['macd']['signal']:.2f}",
                f"BOLL：{analysis['indicators']['bollinger_bands']['lower']:.2f} - {analysis['indicators']['bollinger_bands']['upper']:.2f}",
                f"ATR：{analysis['indicators']['atr']:.2f} / VOL-MA：{analysis['indicators']['volume_ma']:.2f}",
                f"止盈/止损：{current_strategy['config']['take_profit_pct']}% / {current_strategy['config']['stop_loss_pct']}%",
                f"当前信号：{analysis['signal']['signal']}",
                f"Agent 决策：{analysis['agent']['decision']}",
                f"风险预检：{analysis['risk_preview']['reason']}",
            ],
        },
        "historical_strategies": [*strategy_items],
        "trade_records": [
            {
                "strategy": item.get("strategy_name", ""),
                "side": "买入" if item.get("side") == "buy" else "卖出" if item.get("side") == "sell" else item.get("side", ""),
                "created_at": item.get("timestamp", ""),
            }
            for item in trade_record_store.list_all()
        ],
        "account_metrics": account_metrics,
        "sources": sources,
        "daily_report": daily_report,
        "analysis": analysis,
    }


def build_prompt_preview_context(symbol: str = None) -> dict:
    symbol = symbol or settings.default_symbol
    timeframe = "1h"
    strategy_name = "sma_crossover"
    candles = market_data_service._get_demo_candles(symbol=symbol, timeframe=timeframe, limit=20)
    analysis = quant_engine.analyze_market(
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=strategy_name,
        strategy_config={},
        candles=candles,
    )
    sources = build_news_sources_view(symbol=symbol, force_llm_summary=False)
    account_metrics = {
        "progress": max(10, round(analysis["agent"]["confidence"] * 100)),
        "total_asset": 10000,
        "coin_asset": f"{symbol} / {analysis['signal']['signal']}",
        "yield_rate": round((analysis["agent"]["confidence"] - 0.5) * 20, 2),
        "positions": [
            {"asset": "USDT", "balance": 8200, "available": 7600},
            {"asset": "BTC", "balance": 0.021, "available": 0.018},
        ],
        "trend": [],
        "candles": candles,
    }
    daily_report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sections": analysis_chain_service.build_fallback_daily_report(
            symbol=symbol,
            analysis=analysis,
            account_metrics=account_metrics,
        ),
    }
    return {
        "symbol": symbol,
        "analysis": analysis,
        "sources": sources,
        "account_metrics": account_metrics,
        "daily_report": daily_report,
    }


def build_prompt_preview_context_for_strategy(symbol: str = None, strategy_name: str = None, timeframe: str = None) -> dict:
    symbol = symbol or settings.default_symbol
    strategy_name = strategy_name or "sma_crossover"
    timeframe = timeframe or "1h"
    candles = market_data_service.get_candles(symbol=symbol, timeframe=timeframe, limit=20)
    analysis = quant_engine.analyze_market(
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=strategy_name,
        strategy_config=(strategy_store.get(strategy_name) or {}).get("config", {}),
        candles=candles,
    )
    sources = build_news_sources_view(symbol=symbol, force_llm_summary=False)
    account_overview = okx_executor.get_account_overview()
    account_metrics = {
        "progress": max(10, round(analysis["agent"]["confidence"] * 100)),
        "total_asset": float(account_overview.get("total_equity", 0) or 0),
        "coin_asset": f"{symbol} / {analysis['signal']['signal']}",
        "yield_rate": round((analysis["agent"]["confidence"] - 0.5) * 20, 2),
        "positions": [
            {
                "asset": item.get("asset", ""),
                "balance": float(item.get("equity", item.get("balance", 0)) or 0),
                "available": float(item.get("available", 0) or 0),
            }
            for item in account_overview.get("assets", [])
        ],
        "trend": [],
        "candles": candles,
    }
    daily_report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sections": analysis_chain_service.build_fallback_daily_report(
            symbol=symbol,
            analysis=analysis,
            account_metrics=account_metrics,
        ),
    }
    return {
        "symbol": symbol,
        "analysis": analysis,
        "sources": sources,
        "account_metrics": account_metrics,
        "daily_report": daily_report,
    }


automation_service = AutomationService(
    runtime_config_service=runtime_config_service,
    strategy_store=strategy_store,
    trading_orchestrator=trading_orchestrator,
    backtest_store=backtest_store,
    trade_record_store=trade_record_store,
    learning_service=learning_service,
    notification_service=notification_service,
    snapshot_builder=build_dashboard_snapshot,
)
task_service = TaskService()


def _render_news_source(source: dict, symbol: str, force_llm_summary: Optional[bool] = None) -> dict:
    meta = source.get("meta", {})
    use_llm_summary = force_llm_summary if force_llm_summary is not None else bool(meta.get("llm_summary", False))
    summary_mode = "llm" if use_llm_summary else "raw"
    summary_error = ""
    try:
        items = (
            analysis_chain_service.summarize_news(symbol=symbol, source_name=source["name"], items=source["items"])
            if use_llm_summary
            else analysis_chain_service.build_fallback_news_cards(source_name=source["name"], items=source["items"])
        )
    except Exception as exc:
        items = analysis_chain_service.build_fallback_news_cards(source_name=source["name"], items=source["items"])
        summary_mode = "raw-fallback"
        summary_error = str(exc)
    return {
        "name": source["name"],
        "meta": {**meta, "summary_mode": summary_mode, "summary_error": summary_error},
        "items": items,
    }


def build_news_sources_view(symbol: str, force_llm_summary: Optional[bool] = None) -> list[dict]:
    raw_sources = news_rag_service.list_sources(symbol=symbol)
    return [_render_news_source(source, symbol=symbol, force_llm_summary=force_llm_summary) for source in raw_sources]


def build_single_news_source_view(source_name: str, symbol: str, force_llm_summary: Optional[bool] = None) -> dict:
    raw_sources = news_rag_service.list_sources(symbol=symbol)
    source = next((item for item in raw_sources if item.get("name") == source_name), None)
    if source is None:
        raise ValueError(f"未找到新闻源：{source_name}")
    return _render_news_source(source, symbol=symbol, force_llm_summary=force_llm_summary)
