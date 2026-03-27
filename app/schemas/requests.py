from pydantic import BaseModel, Field


class StrategyAnalysisRequest(BaseModel):
    symbol: str = Field(default="BTC-USDT-SWAP")
    timeframe: str = Field(default="1h")
    strategy_name: str = Field(default="sma_crossover")


class BacktestRequest(BaseModel):
    symbol: str = Field(default="BTC-USDT-SWAP")
    timeframe: str = Field(default="1h")
    strategy_name: str = Field(default="sma_crossover")
    initial_capital: float = Field(default=10000.0, gt=0)
    bars: int = Field(default=120, ge=30, le=1000)


class TradeExecutionRequest(BaseModel):
    symbol: str = Field(default="BTC-USDT-SWAP")
    side: str = Field(default="buy")
    size: float = Field(default=0.01, gt=0)
    strategy_name: str = Field(default="sma_crossover")
