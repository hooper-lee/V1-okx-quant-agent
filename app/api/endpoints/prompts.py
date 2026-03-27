from fastapi import APIRouter

from datetime import datetime

from app.core.container import build_prompt_preview_context_for_strategy, news_rag_service, prompt_template_service, task_service
from app.schemas.prompt import PromptPreviewRequest, PromptUpdateRequest

router = APIRouter()

PROMPT_META = {
    "market_summary": {
        "label": "市场摘要",
        "category": "分析链",
        "description": "把技术指标和信号整理成市场概览，供后续 Agent 与日报使用。",
    },
    "agent_decision": {
        "label": "Agent 决策",
        "category": "决策链",
        "description": "结合策略信号、新闻上下文和记忆，输出结构化 JSON 决策：market_view / confidence / action / symbol / position_size / reason。",
    },
    "daily_report": {
        "label": "每日日报",
        "category": "报告生成",
        "description": "生成日报四段式内容：市场摘要、策略结论、风险提醒、操作建议。",
    },
    "news_digest": {
        "label": "新闻摘要",
        "category": "RAG 摘要",
        "description": "把多源新闻压缩成适合看板展示的卡片内容。",
    },
    "daily_reflection": {
        "label": "每日自动总结",
        "category": "学习沉淀",
        "description": "把日报、分析、回测和交易结果整理成适合写入长期记忆的复盘总结。",
    },
}


@router.get("")
def list_prompts() -> dict:
    items = []
    for item in prompt_template_service.list_templates():
        meta = PROMPT_META.get(item["name"], {})
        items.append({**item, **meta})
    return {"items": items}


@router.get("/{name}")
def get_prompt(name: str) -> dict:
    item = prompt_template_service.get_template(name)
    return {"item": {**item, **PROMPT_META.get(name, {})}}


@router.put("/{name}")
def update_prompt(name: str, payload: PromptUpdateRequest) -> dict:
    return {"item": prompt_template_service.save_template(name=name, content=payload.content)}


@router.post("/preview/{name}")
def preview_prompt(name: str, payload: PromptPreviewRequest) -> dict:
    try:
        context = build_prompt_preview_context_for_strategy(
            symbol=payload.symbol,
            strategy_name=payload.strategy_name,
            timeframe=payload.timeframe,
        )
        symbol = context["symbol"]
        analysis = context["analysis"]
        sources = context["sources"]
        first_source = sources[0] if sources else {"name": "news", "items": []}
        demo_daily_report = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sections": [
                {"title": "市场摘要", "body": f"当前监控标的为 {symbol}，最新价格 {analysis['last_price']}，短线信号为 {analysis['signal']['signal']}，主周期 {analysis['timeframe']}。"},
                {"title": "策略结论", "body": f"当前启用策略 {analysis['strategy_name']}，Agent 决策为 {analysis['agent']['decision']}，置信度约 {max(10, round(analysis['agent']['confidence'] * 100))}%。"},
                {"title": "风险提醒", "body": f"风险预检结果为 {analysis['risk_preview']['reason']}，当前更适合控制仓位而不是主动追价。"},
                {"title": "操作建议", "body": "建议继续观察趋势确认与量能变化，再决定是否增加风险暴露。"},
            ],
        }
        if name == "daily_report":
            return {"ok": True, "item": demo_daily_report}
        if name == "news_digest":
            return {"ok": True, "item": {"source": first_source["name"], "cards": first_source["items"]}}
        if name == "market_summary":
            return {"ok": True, "item": {"text": f"{symbol} market snapshot: signal={analysis['signal']['signal']}, reason={analysis['signal']['reason']}, RSI={analysis['indicators']['rsi']:.2f}, SMA fast={analysis['indicators']['sma_fast']:.2f}, SMA slow={analysis['indicators']['sma_slow']:.2f}."}}
        if name == "agent_decision":
            structured = analysis["agent"].get("structured") or {
                "market_view": analysis["agent"].get("market_view"),
                "confidence": analysis["agent"].get("confidence"),
                "action": analysis["agent"].get("action") or analysis["agent"].get("decision"),
                "symbol": analysis["agent"].get("symbol") or analysis["symbol"],
                "position_size": analysis["agent"].get("position_size"),
                "reason": analysis["agent"].get("reason") or [analysis["agent"].get("rationale")],
            }
            return {
                "ok": True,
                "item": {
                    "decision": analysis["agent"]["decision"],
                    "confidence": analysis["agent"]["confidence"],
                    "rationale": analysis["agent"]["rationale"],
                    "structured": structured,
                },
            }
        return {"ok": False, "item": {"message": f"{name} 暂无预览实现。"}}
    except Exception as exc:
        return {"ok": False, "item": {"message": f"预览失败：{exc}"}}


@router.post("/preview-async/{name}")
def preview_prompt_async(name: str, payload: PromptPreviewRequest) -> dict:
    item = task_service.create_task(
        label=f"prompt-preview:{name}",
        runner=lambda: preview_prompt(name=name, payload=payload),
    )
    return {"item": item}
