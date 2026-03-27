from typing import Optional


class AgentDecisionService:
    def __init__(self, chain_service, rag_service, memory_service, runtime, prompt_template_service) -> None:
        self.chain_service = chain_service
        self.rag_service = rag_service
        self.memory_service = memory_service
        self.runtime = runtime
        self.prompt_template_service = prompt_template_service

    def _normalize_action(self, value: object, fallback: str = "hold") -> str:
        action = str(value or fallback).strip().lower()
        return action if action in {"buy", "sell", "hold"} else fallback

    def _normalize_confidence(self, value: object, fallback: float = 0.5) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = fallback
        return max(0.0, min(confidence, 1.0))

    def _normalize_reason(self, parsed: dict, summary: str) -> list[str]:
        raw_reason = parsed.get("reason")
        if isinstance(raw_reason, list):
            items = [str(item).strip() for item in raw_reason if str(item).strip()]
            if items:
                return items
        if isinstance(raw_reason, str) and raw_reason.strip():
            return [raw_reason.strip()]

        raw_rationale = parsed.get("rationale")
        if isinstance(raw_rationale, list):
            items = [str(item).strip() for item in raw_rationale if str(item).strip()]
            if items:
                return items
        if isinstance(raw_rationale, str) and raw_rationale.strip():
            return [raw_rationale.strip()]
        return [summary]

    def _infer_market_view(self, action: str, signal: dict, confidence: float) -> str:
        if action == "buy":
            return "short-term bullish" if confidence >= 0.6 else "bullish watch"
        if action == "sell":
            return "short-term bearish" if confidence >= 0.6 else "bearish watch"
        if str(signal.get("signal", "")).lower() in {"buy", "sell"}:
            return "neutral wait"
        return "sideways neutral"

    def _build_response(
        self,
        *,
        symbol: str,
        signal: dict,
        summary: str,
        context: dict,
        memory: str,
        parsed: dict,
    ) -> dict:
        action = self._normalize_action(parsed.get("action") or parsed.get("decision"), signal.get("signal", "hold"))
        confidence = self._normalize_confidence(parsed.get("confidence"), 0.5)
        reason = self._normalize_reason(parsed, summary)
        market_view = str(parsed.get("market_view") or self._infer_market_view(action, signal, confidence))
        rationale = str(parsed.get("rationale") or "；".join(reason))
        position_size = parsed.get("position_size")
        try:
            position_size = max(float(position_size), 0.0) if position_size is not None else None
        except (TypeError, ValueError):
            position_size = None

        structured = {
            "market_view": market_view,
            "confidence": confidence,
            "action": action,
            "symbol": str(parsed.get("symbol") or symbol),
            "position_size": position_size,
            "reason": reason,
        }
        return {
            "summary": summary,
            "context": context,
            "memory": memory,
            "decision": action,
            "confidence": confidence,
            "rationale": rationale,
            "market_view": market_view,
            "action": action,
            "symbol": structured["symbol"],
            "position_size": position_size,
            "reason": reason,
            "structured": structured,
        }

    def decide(self, symbol: str, indicators: dict, signal: Optional[dict] = None) -> dict:
        signal = signal or {"signal": "hold", "reason": "No strategy provided."}
        summary = self.chain_service.summarize_market(symbol=symbol, indicators=indicators, signal=signal)
        context = self.rag_service.retrieve_context(symbol=symbol)
        memory = self.memory_service.recall(symbol=symbol)

        parsed = self.runtime.invoke_json(
            system_prompt=self.prompt_template_service.render("agent_decision"),
            user_prompt=(
                f"symbol={symbol}\nindicators={indicators}\nstrategy_signal={signal}\n"
                f"news={context['news']}\nmemory={memory}\n"
                "decision must be buy, sell, or hold."
            ),
        )
        if parsed:
            return self._build_response(symbol=symbol, signal=signal, summary=summary, context=context, memory=memory, parsed=parsed)

        score = 0
        if indicators["sma_fast"] > indicators["sma_slow"]:
            score += 1
        if indicators["rsi"] < 70:
            score += 1
        if indicators["rsi"] < 35:
            score += 1
        action = signal["signal"] if signal["signal"] != "hold" else ("buy" if score >= 2 else "hold")
        return self._build_response(
            symbol=symbol,
            signal=signal,
            summary=summary,
            context=context,
            memory=memory,
            parsed={
                "decision": action,
                "confidence": min(score / 3, 1.0),
                "rationale": "Fallback heuristic path used because runtime model is unavailable.",
            },
        )
