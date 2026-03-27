from fastapi import APIRouter

from app.core.container import market_data_service

router = APIRouter()


@router.get("/candles")
def get_candles(symbol: str = "BTC-USDT-SWAP", timeframe: str = "1h", limit: int = 50) -> dict:
    candles = market_data_service.get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    return {"symbol": symbol, "timeframe": timeframe, "count": len(candles), "data": candles}
