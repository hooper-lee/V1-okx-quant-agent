from pydantic import BaseModel, Field


class BacktestSaveRequest(BaseModel):
    label: str = Field(default="Backtest Run", min_length=2, max_length=100)
    symbol: str = Field(default="BTC-USDT-SWAP", min_length=3, max_length=50)
    timeframe: str = Field(default="1h", min_length=1, max_length=10)
    strategy_name: str = Field(default="sma_crossover", min_length=2, max_length=50)
    initial_capital: float = Field(default=10000.0, gt=0)
    result: dict = Field(default_factory=dict)


class BacktestCompareRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=6)
