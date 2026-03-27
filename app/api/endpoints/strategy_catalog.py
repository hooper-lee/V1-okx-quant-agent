import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.container import langchain_runtime, prompt_template_service, strategy_store
from app.schemas.strategy import StrategyCreateRequest, StrategySuggestionRequest, StrategyUpdateRequest

router = APIRouter()


DEFAULT_STRATEGY_TEMPLATES = [
    {
        "key": "conservative",
        "label": "保守",
        "strategy_type": "reversal",
        "risk_preference": "conservative",
        "description": "偏保守的均值回归模板，优先控制回撤和仓位占用。",
        "execution_notes": "优先等待极值区确认后轻仓分批入场，触及回撤上限后暂停执行。",
        "config": {
            "timeframe": "4h",
            "leverage": 1.0,
            "margin_mode": "cross",
            "entry_allocation_pct": 12.0,
            "max_position_pct": 28.0,
            "max_drawdown_limit_pct": 8.0,
            "fast_period": 8,
            "slow_period": 24,
            "rsi_period": 16,
            "take_profit_pct": 5.0,
            "stop_loss_pct": 2.0,
            "risk_limit_pct": 1.0,
        },
    },
    {
        "key": "balanced",
        "label": "平衡",
        "strategy_type": "trend",
        "risk_preference": "balanced",
        "description": "平衡型趋势模板，在收益和稳定性之间取中间值。",
        "execution_notes": "趋势确认后按节奏建仓，仓位和回撤都保持在可控区间。",
        "config": {
            "timeframe": "1h",
            "leverage": 2.0,
            "margin_mode": "cross",
            "entry_allocation_pct": 22.0,
            "max_position_pct": 45.0,
            "max_drawdown_limit_pct": 12.0,
            "fast_period": 7,
            "slow_period": 20,
            "rsi_period": 14,
            "take_profit_pct": 8.0,
            "stop_loss_pct": 3.0,
            "risk_limit_pct": 2.0,
        },
    },
    {
        "key": "aggressive",
        "label": "激进",
        "strategy_type": "hybrid",
        "risk_preference": "aggressive",
        "description": "偏激进的混合模板，强调收益弹性和更快的节奏切换。",
        "execution_notes": "允许更高杠杆和更高开仓占比，但需要更频繁地检查信号衰减和风控阈值。",
        "config": {
            "timeframe": "15m",
            "leverage": 3.0,
            "margin_mode": "isolated",
            "entry_allocation_pct": 32.0,
            "max_position_pct": 65.0,
            "max_drawdown_limit_pct": 16.0,
            "fast_period": 5,
            "slow_period": 18,
            "rsi_period": 10,
            "take_profit_pct": 10.0,
            "stop_loss_pct": 3.8,
            "risk_limit_pct": 3.0,
        },
    },
]


@router.get("/templates")
def list_strategy_templates() -> dict:
    return {"items": DEFAULT_STRATEGY_TEMPLATES}


@router.get("")
def list_strategies() -> dict:
    return {"items": strategy_store.list_all()}


@router.get("/{name}")
def get_strategy(name: str) -> dict:
    item = strategy_store.get(name)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"item": item}


@router.post("")
def create_strategy(payload: StrategyCreateRequest) -> dict:
    try:
        item = strategy_store.add(
            {
                "name": payload.name,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": payload.strategy_type,
                "risk_preference": payload.risk_preference,
                "description": payload.description,
                "execution_notes": payload.execution_notes,
                "config": {
                    "symbol": payload.symbol,
                    "timeframe": payload.timeframe,
                    "target_capital": payload.target_capital,
                    "target_horizon_days": payload.target_horizon_days,
                    "leverage": payload.leverage,
                    "entry_allocation_pct": payload.entry_allocation_pct,
                    "max_position_pct": payload.max_position_pct,
                    "max_drawdown_limit_pct": payload.max_drawdown_limit_pct,
                    "margin_mode": payload.margin_mode,
                    "fast_period": payload.fast_period,
                    "slow_period": payload.slow_period,
                    "rsi_period": payload.rsi_period,
                    "take_profit_pct": payload.take_profit_pct,
                    "stop_loss_pct": payload.stop_loss_pct,
                    "risk_limit_pct": payload.risk_limit_pct,
                },
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"item": item}


@router.put("/{name}")
def update_strategy(name: str, payload: StrategyUpdateRequest) -> dict:
    item = strategy_store.update(
        name,
        {
            "type": payload.strategy_type,
            "risk_preference": payload.risk_preference,
            "description": payload.description,
            "execution_notes": payload.execution_notes,
            "config": {
                "symbol": payload.symbol,
                "timeframe": payload.timeframe,
                "target_capital": payload.target_capital,
                "target_horizon_days": payload.target_horizon_days,
                "leverage": payload.leverage,
                "entry_allocation_pct": payload.entry_allocation_pct,
                "max_position_pct": payload.max_position_pct,
                "max_drawdown_limit_pct": payload.max_drawdown_limit_pct,
                "margin_mode": payload.margin_mode,
                "fast_period": payload.fast_period,
                "slow_period": payload.slow_period,
                "rsi_period": payload.rsi_period,
                "take_profit_pct": payload.take_profit_pct,
                "stop_loss_pct": payload.stop_loss_pct,
                "risk_limit_pct": payload.risk_limit_pct,
            },
        },
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"item": item}


@router.post("/suggest")
def suggest_strategy(payload: StrategySuggestionRequest) -> dict:
    item = _normalize_suggestion(payload, None, source="heuristic")
    return {"item": item}


@router.post("/suggest-ai")
def suggest_strategy_ai(payload: StrategySuggestionRequest) -> dict:
    prompt_payload = {
        "name": payload.name,
        "strategy_type": payload.strategy_type,
        "symbol": payload.symbol,
        "target_capital": payload.target_capital,
        "target_horizon_days": payload.target_horizon_days,
        "risk_preference": payload.risk_preference,
        "leverage": payload.leverage,
    }
    suggestion = langchain_runtime.invoke_json(
        system_prompt=prompt_template_service.render("strategy_suggestion"),
        user_prompt=json.dumps(prompt_payload, ensure_ascii=False),
    )
    if suggestion is None:
        raise HTTPException(
            status_code=503,
            detail=langchain_runtime._last_error or "AI 建议生成失败，请检查模型配置或连接状态。",
        )
    item = _normalize_suggestion(payload, suggestion, source="llm")
    return {"item": item}


def _normalize_suggestion(payload: StrategySuggestionRequest, suggestion: Optional[dict], source: str) -> dict:
    horizon = payload.target_horizon_days
    capital = payload.target_capital
    fallback_timeframe = "15m" if horizon <= 7 else "1h" if horizon <= 30 else "4h" if horizon <= 90 else "1d"
    fallback_type = "trend" if horizon <= 30 else "hybrid"
    fallback_risk_limit = 1.0 if capital >= 100000 else 1.5 if capital >= 30000 else 2.0
    fallback_entry_allocation = 12.0 if payload.risk_preference == "conservative" else 22.0 if payload.risk_preference == "balanced" else 32.0
    fallback_max_position = 28.0 if payload.risk_preference == "conservative" else 45.0 if payload.risk_preference == "balanced" else 65.0
    fallback_drawdown_limit = 8.0 if payload.risk_preference == "conservative" else 12.0 if payload.risk_preference == "balanced" else 16.0
    fallback_leverage = payload.leverage or (1.0 if payload.risk_preference == "conservative" else 2.0 if payload.risk_preference == "balanced" else 3.0)
    fallback_margin_mode = "cross" if payload.risk_preference != "aggressive" else "isolated"
    item = suggestion or {}
    fallback_description = (
        f"面向目标资金 {payload.target_capital:.0f}、目标周期 {payload.target_horizon_days} 天的建议策略，"
        f"优先兼顾风险控制与执行稳定性。"
    )
    fallback_notes = (
        f"建议采用 {payload.risk_preference} 风险偏好，在 {fallback_timeframe} 周期下观察趋势确认后分批执行，"
        f"单笔风险控制在 {fallback_risk_limit:.1f}% 左右。"
    )
    return {
        "name": payload.name,
        "strategy_type": str(item.get("strategy_type") or fallback_type),
        "risk_preference": payload.risk_preference,
        "symbol": payload.symbol,
        "description": str(item.get("description") or fallback_description),
        "execution_notes": str(item.get("execution_notes") or item.get("rationale") or fallback_notes),
        "timeframe": str(item.get("timeframe") or fallback_timeframe),
        "target_capital": payload.target_capital,
        "target_horizon_days": payload.target_horizon_days,
        "leverage": float(item.get("leverage") or fallback_leverage),
        "entry_allocation_pct": float(item.get("entry_allocation_pct") or fallback_entry_allocation),
        "max_position_pct": float(item.get("max_position_pct") or fallback_max_position),
        "max_drawdown_limit_pct": float(item.get("max_drawdown_limit_pct") or fallback_drawdown_limit),
        "margin_mode": str(item.get("margin_mode") or fallback_margin_mode),
        "fast_period": int(item.get("fast_period") or (5 if horizon <= 7 else 7 if horizon <= 30 else 12)),
        "slow_period": int(item.get("slow_period") or (18 if horizon <= 7 else 20 if horizon <= 30 else 30)),
        "rsi_period": int(item.get("rsi_period") or (10 if horizon <= 7 else 14 if horizon <= 90 else 21)),
        "take_profit_pct": float(item.get("take_profit_pct") or (4.0 if horizon <= 7 else 8.0 if horizon <= 30 else 12.0)),
        "stop_loss_pct": float(item.get("stop_loss_pct") or (1.5 if horizon <= 7 else 3.0 if horizon <= 30 else 5.0)),
        "risk_limit_pct": float(item.get("risk_limit_pct") or fallback_risk_limit),
        "source": source,
    }
