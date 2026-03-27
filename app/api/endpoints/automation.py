from fastapi import APIRouter
from typing import Optional

from app.core.container import automation_service, task_service
from app.schemas.automation import AutomationConfigRequest

router = APIRouter()


@router.get("/status")
def get_automation_status() -> dict:
    return {"item": automation_service.status()}


@router.put("/config")
def update_automation_config(payload: AutomationConfigRequest) -> dict:
    item = automation_service.update_config(payload.model_dump())
    return {"item": item}


@router.post("/auto-trade/run")
async def run_auto_trade_once() -> dict:
    return {"item": await automation_service.run_auto_trade_once()}


@router.post("/daily-summary/run")
async def run_daily_summary_once(force: bool = True) -> dict:
    return {"item": await automation_service.run_daily_summary_once(force=force)}


@router.post("/daily-summary/run-async")
def run_daily_summary_once_async(force: bool = True) -> dict:
    item = task_service.create_task(
        label="daily-summary",
        runner=lambda: automation_service.run_daily_summary_once(force=force),
    )
    return {"item": item}


@router.get("/daily-summary/history")
def get_daily_summary_history(strategy_name: Optional[str] = None, limit: int = 10) -> dict:
    items = automation_service.learning_service.list_daily_summaries(strategy_name=strategy_name or "", limit=max(1, min(limit, 50)))
    return {"items": items}
