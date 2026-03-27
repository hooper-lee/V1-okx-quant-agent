from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUNTIME_CONFIG_PATH = BASE_DIR / ".runtime-config.json"
STRATEGY_STORE_PATH = BASE_DIR / ".strategies.json"
MEMORY_STORE_PATH = BASE_DIR / ".memory-store.json"


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    app_name: str = "OKX Quant Agent"
    environment: str = os.getenv("APP_ENV", "development")
    app_password: str = os.getenv("APP_PASSWORD", "")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    llm_model: str = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    embeddings_provider: str = os.getenv("EMBEDDINGS_PROVIDER", "openai")
    embeddings_model: str = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")
    chroma_persist_directory: str = os.getenv("CHROMA_PERSIST_DIRECTORY", str(BASE_DIR / ".chroma"))
    memory_store_path: str = os.getenv("MEMORY_STORE_PATH", str(MEMORY_STORE_PATH))

    okx_rest_base: str = os.getenv("OKX_REST_BASE", "https://www.okx.com")
    okx_api_key: str = os.getenv("OKX_API_KEY", "")
    okx_api_secret: str = os.getenv("OKX_API_SECRET", "")
    okx_passphrase: str = os.getenv("OKX_PASSPHRASE", "")
    okx_use_paper: bool = _to_bool(os.getenv("OKX_USE_PAPER"), True)

    default_symbol: str = os.getenv("DEFAULT_SYMBOL", "BTC-USDT-SWAP")
    max_order_notional: float = Field(default=float(os.getenv("MAX_ORDER_NOTIONAL", "10000")))
    risk_per_trade: float = Field(default=float(os.getenv("RISK_PER_TRADE", "0.02")))
    use_live_services: bool = _to_bool(os.getenv("USE_LIVE_SERVICES"), True)


settings = Settings()
