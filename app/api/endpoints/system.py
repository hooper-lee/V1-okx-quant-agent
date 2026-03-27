from fastapi import APIRouter
from typing import Optional

from app.core.container import (
    analysis_chain_service,
    automation_service,
    build_system_overview,
    build_dashboard_snapshot,
    langchain_runtime,
    market_data_service,
    news_rag_service,
    okx_client,
    prompt_template_service,
    quant_engine,
    strategy_store,
    task_service,
)

router = APIRouter()


@router.get("/overview")
def get_overview() -> dict:
    return build_system_overview()


@router.post("/self-check")
def run_self_check(strategy_name: Optional[str] = None) -> dict:
    strategy = strategy_store.get(strategy_name or "sma_crossover") or strategy_store.list_all()[0]
    symbol = strategy.get("config", {}).get("symbol", "BTC-USDT-SWAP")
    timeframe = strategy.get("config", {}).get("timeframe", "1h")
    initial_capital = float(strategy.get("config", {}).get("target_capital", 10000) or 10000)

    checks: list[dict] = []

    llm_result = langchain_runtime.test_connection()
    checks.append(
        {
            "key": "llm",
            "label": "LLM",
            "status": "normal" if llm_result.get("ok") else "failed",
            "message": llm_result.get("message", ""),
            "detail": llm_result,
        }
    )

    try:
        news_items = news_rag_service.list_sources(symbol=symbol)
        statuses = [item.get("meta", {}).get("status", "pending") for item in news_items]
        if news_items and all(status == "success" for status in statuses):
            status = "normal"
        elif news_items and any(status in {"fallback", "pending", "seeded"} for status in statuses):
            status = "fallback"
        else:
            status = "failed"
        checks.append(
            {
                "key": "news",
                "label": "新闻源",
                "status": status,
                "message": " | ".join(f"{item['name']}:{item.get('meta', {}).get('status', 'unknown')}" for item in news_items) or "未配置新闻源",
                "detail": news_items,
            }
        )
    except Exception as exc:
        checks.append({"key": "news", "label": "新闻源", "status": "failed", "message": str(exc), "detail": {"error": str(exc)}})

    try:
        snapshot = build_dashboard_snapshot(strategy_name=strategy["name"])
        account_source = snapshot.get("account_metrics", {}).get("account_overview", {}).get("source", "demo")
        snapshot_status = "normal" if account_source == "okx-live" else "fallback"
        checks.append(
            {
                "key": "dashboard",
                "label": "看板快照",
                "status": snapshot_status,
                "message": f"{snapshot['current_strategy']['name']} / {snapshot['analysis']['symbol']} / {account_source}",
                "detail": {
                    "current_strategy": snapshot["current_strategy"]["name"],
                    "symbol": snapshot["analysis"]["symbol"],
                    "timeframe": snapshot["analysis"]["timeframe"],
                    "account_source": account_source,
                },
            }
        )
    except Exception as exc:
        checks.append({"key": "dashboard", "label": "看板快照", "status": "failed", "message": str(exc), "detail": {"error": str(exc)}})

    try:
        backtest = quant_engine.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=strategy["name"],
            initial_capital=initial_capital,
            bars=60,
            strategy_config=strategy.get("config", {}),
        )
        ticker = market_data_service.get_ticker(symbol=symbol)
        backtest_status = "normal" if ticker.get("source") == "okx-live" else "fallback"
        checks.append(
            {
                "key": "backtest",
                "label": "回测",
                "status": backtest_status,
                "message": f"trades={backtest.get('trade_count', 0)} / return={backtest.get('total_return_pct', 0)}%",
                "detail": {
                    "trade_count": backtest.get("trade_count", 0),
                    "total_return_pct": backtest.get("total_return_pct", 0),
                    "max_drawdown_pct": backtest.get("max_drawdown_pct", 0),
                    "data_source": ticker.get("source", "demo"),
                },
            }
        )
    except Exception as exc:
        checks.append({"key": "backtest", "label": "回测", "status": "failed", "message": str(exc), "detail": {"error": str(exc)}})

    public_result = okx_client.test_public_connection(symbol=symbol)
    private_result = okx_client.test_private_connection()
    okx_status = "normal" if public_result.get("ok") and private_result.get("ok") else "fallback" if public_result.get("ok") else "failed"
    checks.append(
        {
            "key": "okx",
            "label": "OKX",
            "status": okx_status,
            "message": f"public={public_result.get('message', '')} / private={private_result.get('message', '')}",
            "detail": {
                "public": public_result,
                "private": private_result,
                "candidates": okx_client.diagnose_candidates(symbol=symbol),
            },
        }
    )

    try:
        heuristic = (
            f"{symbol} market snapshot: signal=hold, reason=preview check, timeframe={timeframe}, strategy={strategy['name']}."
        )
        prompt_result = langchain_runtime.invoke_text(
            system_prompt=prompt_template_service.render("market_summary"),
            user_prompt=heuristic,
        )
        prompt_status = "normal" if prompt_result else "fallback"
        if not prompt_result:
            prompt_result = analysis_chain_service.summarize_market(
                symbol=symbol,
                indicators={"rsi": 50.0, "sma_fast": 1.0, "sma_slow": 1.0},
                signal={"signal": "hold", "reason": "preview fallback"},
            )
        checks.append(
            {
                "key": "prompt_preview",
                "label": "Prompt 预览",
                "status": prompt_status,
                "message": "模板可生成预览结果" if prompt_result else "模板预览为空",
                "detail": {"preview": prompt_result},
            }
        )
    except Exception as exc:
        checks.append({"key": "prompt_preview", "label": "Prompt 预览", "status": "failed", "message": str(exc), "detail": {"error": str(exc)}})

    overall = "normal"
    if any(item["status"] == "failed" for item in checks):
        overall = "failed"
    elif any(item["status"] == "fallback" for item in checks):
        overall = "fallback"

    return {
        "item": {
            "overall": overall,
            "strategy_name": strategy["name"],
            "symbol": symbol,
            "timeframe": timeframe,
            "automation": automation_service.status(),
            "checks": checks,
        }
    }


@router.post("/self-check-async")
def run_self_check_async(strategy_name: Optional[str] = None) -> dict:
    item = task_service.create_task(
        label="system-self-check",
        runner=lambda: run_self_check(strategy_name=strategy_name),
    )
    return {"item": item}
