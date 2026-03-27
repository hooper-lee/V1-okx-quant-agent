import json
from datetime import datetime
from typing import Optional


class AnalysisChainService:
    def __init__(self, runtime, prompt_template_service) -> None:
        self.runtime = runtime
        self.prompt_template_service = prompt_template_service

    def summarize_market(self, symbol: str, indicators: dict, signal: Optional[dict] = None) -> str:
        signal = signal or {"signal": "hold", "reason": "No explicit strategy signal."}
        heuristic = (
            f"{symbol} market snapshot: signal={signal['signal']}, reason={signal['reason']}, "
            f"RSI={indicators['rsi']:.2f}, SMA fast={indicators['sma_fast']:.2f}, SMA slow={indicators['sma_slow']:.2f}."
        )
        return self.runtime.invoke_text(
            system_prompt=self.prompt_template_service.render("market_summary"),
            user_prompt=heuristic,
        ) or heuristic

    def summarize_news(self, symbol: str, source_name: str, items: list[dict]) -> list[dict]:
        heuristic_cards = self.build_fallback_news_cards(source_name=source_name, items=items)
        payload = {
            "symbol": symbol,
            "source": source_name,
            "items": heuristic_cards,
        }
        parsed = self.runtime.invoke_json(
            system_prompt=self.prompt_template_service.render("news_digest"),
            user_prompt=json.dumps(payload, ensure_ascii=False),
        )
        if parsed and isinstance(parsed.get("cards"), list):
            cards = []
            for item in parsed["cards"]:
                cards.append(
                    {
                        "title": item.get("title", f"{source_name} update"),
                        "body": item.get("body", ""),
                        "source": item.get("source", source_name),
                    }
                )
            if cards:
                return cards
        return heuristic_cards

    def build_fallback_news_cards(self, source_name: str, items: list[dict]) -> list[dict]:
        return [
            {
                "title": item.get("title", f"{source_name} update"),
                "body": item.get("summary", ""),
                "source": item.get("source", source_name),
            }
            for item in items
        ]

    def generate_daily_report(self, symbol: str, analysis: dict, account_metrics: dict, news_context: list[dict]) -> dict:
        fallback_sections = self.build_fallback_daily_report(symbol=symbol, analysis=analysis, account_metrics=account_metrics)
        payload = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "symbol": symbol,
            "analysis": {
                "strategy_name": analysis["strategy_name"],
                "timeframe": analysis["timeframe"],
                "signal": analysis["signal"],
                "agent": analysis["agent"],
                "risk_preview": analysis["risk_preview"],
                "last_price": analysis["last_price"],
            },
            "account_metrics": account_metrics,
            "news_context": news_context[:4],
        }
        parsed = self.runtime.invoke_json(
            system_prompt=self.prompt_template_service.render("daily_report"),
            user_prompt=json.dumps(payload, ensure_ascii=False),
        )
        if parsed and isinstance(parsed.get("sections"), list):
            sections = [
                {"title": item.get("title", "未命名"), "body": item.get("body", "")}
                for item in parsed["sections"]
                if item.get("body")
            ]
            if sections:
                return {"date": payload["date"], "sections": sections}
        return {"date": payload["date"], "sections": fallback_sections}

    def build_fallback_daily_report(self, symbol: str, analysis: dict, account_metrics: dict) -> list[dict]:
        return [
            {
                "title": "市场摘要",
                "body": f"当前监控标的为 {symbol}，最新价格 {analysis['last_price']}，短线信号为 {analysis['signal']['signal']}，主周期 {analysis['timeframe']}。",
            },
            {
                "title": "策略结论",
                "body": f"当前启用策略 {analysis['strategy_name']}，Agent 决策为 {analysis['agent']['decision']}，置信度约 {max(10, round(analysis['agent']['confidence'] * 100))}%。",
            },
            {
                "title": "风险提醒",
                "body": f"风险预检结果为 {analysis['risk_preview']['reason']}，当前收益率 {account_metrics['yield_rate']}%，建议继续控制仓位暴露。",
            },
            {
                "title": "操作建议",
                "body": "建议结合热点信息源确认趋势是否延续；若波动进一步放大，优先保守执行和缩减仓位。",
            },
        ]
