from fastapi import APIRouter

from app.core.container import okx_executor

router = APIRouter()


@router.get("/overview")
def get_account_overview() -> dict:
    return okx_executor.get_account_overview()


@router.get("/positions")
def get_positions() -> dict:
    return okx_executor.list_positions()


@router.get("/orders")
def get_orders() -> dict:
    return okx_executor.list_orders()
