from pydantic import BaseModel, Field


class PromptUpdateRequest(BaseModel):
    content: str = Field(min_length=1)


class PromptPreviewRequest(BaseModel):
    symbol: str = Field(default="BTC-USDT-SWAP")
    strategy_name: str = Field(default="sma_crossover")
    timeframe: str = Field(default="1h")
