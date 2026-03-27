from fastapi import APIRouter, HTTPException
from typing import Optional

from app.core.container import build_news_sources_view, build_single_news_source_view, news_rag_service
from app.core.config import settings
from app.schemas.news import NewsSourceConfigUpdateRequest

router = APIRouter()


@router.get("/sources")
def get_news_sources(symbol: Optional[str] = None, use_llm: bool = False) -> dict:
    return {"items": build_news_sources_view(symbol=symbol or settings.default_symbol, force_llm_summary=use_llm)}


@router.get("/config")
def get_news_source_config() -> dict:
    return {"items": news_rag_service.get_source_config()}


@router.put("/config")
def update_news_source_config(payload: NewsSourceConfigUpdateRequest) -> dict:
    return {"items": news_rag_service.save_source_config(payload.sources)}


@router.post("/refresh")
def refresh_news_sources(symbol: Optional[str] = None, force: bool = False) -> dict:
    result = news_rag_service.refresh_sources(symbol=symbol or settings.default_symbol, force=force)
    return {"ok": True, **result}


@router.post("/summarize")
def summarize_news_source(source_name: str, symbol: Optional[str] = None) -> dict:
    try:
        item = build_single_news_source_view(source_name=source_name, symbol=symbol or settings.default_symbol, force_llm_summary=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"item": item}
