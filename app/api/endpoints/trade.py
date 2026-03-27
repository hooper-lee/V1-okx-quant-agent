from fastapi import APIRouter, HTTPException

from app.core.container import strategy_store, trading_orchestrator
from app.schemas.requests import TradeExecutionRequest

router = APIRouter()


@router.post("/execute")
def execute_trade(payload: TradeExecutionRequest) -> dict:
    strategy = strategy_store.get(payload.strategy_name)
    result = trading_orchestrator.execute_trade(
        symbol=payload.symbol,
        side=payload.side,
        size=payload.size,
        strategy_name=payload.strategy_name,
        strategy_config={**((strategy or {}).get("config", {}) or {}), "strategy_type": (strategy or {}).get("type", "custom")},
    )
    if result["status"] == "blocked":
        raise HTTPException(status_code=400, detail=result)
    return result
