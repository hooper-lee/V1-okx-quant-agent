from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AutomationConfigRequest(BaseModel):
    auto_trade_enabled: Optional[bool] = None
    auto_trade_interval_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    auto_trade_strategy_names: Optional[list[str]] = None
    auto_trade_min_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    daily_summary_enabled: Optional[bool] = None
    daily_summary_hour: Optional[int] = Field(default=None, ge=0, le=23)
    daily_summary_strategy_names: Optional[list[str]] = None
    daily_summary_apply_ai_updates: Optional[bool] = None
