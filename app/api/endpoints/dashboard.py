from fastapi import APIRouter
from typing import Optional

from app.core.container import build_dashboard_snapshot

router = APIRouter()


@router.get("/snapshot")
def get_dashboard_snapshot(strategy_name: Optional[str] = None) -> dict:
    return build_dashboard_snapshot(strategy_name=strategy_name)
