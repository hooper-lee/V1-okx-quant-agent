from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.core.container import backtest_store, learning_service, quant_engine, strategy_store
from app.schemas.backtest import BacktestCompareRequest, BacktestSaveRequest
from app.schemas.requests import BacktestRequest

router = APIRouter()


@router.post("/run")
def run_backtest(payload: BacktestRequest) -> dict:
    strategy = strategy_store.get(payload.strategy_name)
    return quant_engine.run_backtest(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        strategy_name=payload.strategy_name,
        initial_capital=payload.initial_capital,
        bars=payload.bars,
        strategy_config={**((strategy or {}).get("config", {}) or {}), "strategy_type": (strategy or {}).get("type", "custom")},
    )


@router.post("/save")
def save_backtest(payload: BacktestSaveRequest) -> dict:
    result = payload.result or {}
    run_id = f"bt_{uuid4().hex[:10]}"
    strategy = strategy_store.get(payload.strategy_name)
    item = backtest_store.save(
        {
            "run_id": run_id,
            "label": payload.label,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": payload.symbol,
            "timeframe": payload.timeframe,
            "strategy_name": payload.strategy_name,
            "initial_capital": payload.initial_capital,
            "strategy_config": (strategy or {}).get("config", {}),
            **result,
        }
    )
    try:
        learning_service.store_backtest_summary(item)
    except Exception:
        pass
    return {"item": item}


@router.get("/runs")
def list_backtest_runs() -> dict:
    return {"items": backtest_store.list_all()}


@router.get("/runs/{run_id}")
def get_backtest_run(run_id: str) -> dict:
    item = backtest_store.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return {"item": item}


@router.delete("/runs/{run_id}")
def delete_backtest_run(run_id: str) -> dict:
    item = backtest_store.delete(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return {"item": item}


@router.post("/compare")
def compare_backtest_runs(payload: BacktestCompareRequest) -> dict:
    item = backtest_store.compare(payload.run_ids)
    if not item["items"]:
        raise HTTPException(status_code=404, detail="No backtest runs found for compare request")
    return {"item": item}
