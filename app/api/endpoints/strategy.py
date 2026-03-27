from fastapi import APIRouter

from app.core.container import quant_engine
from app.schemas.requests import StrategyAnalysisRequest

router = APIRouter()


@router.post("/analyze")
def analyze_strategy(payload: StrategyAnalysisRequest) -> dict:
    return quant_engine.analyze_market(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        strategy_name=payload.strategy_name,
    )
