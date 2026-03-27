from __future__ import annotations

import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NotificationService:
    def __init__(self, runtime_config_service) -> None:
        self.runtime_config_service = runtime_config_service

    def config(self) -> dict:
        config = self.runtime_config_service.load()
        return {
            "feishu_webhook_url": str(config.get("feishu_webhook_url") or "").strip(),
            "feishu_push_daily_report": bool(config.get("feishu_push_daily_report", True)),
            "feishu_push_daily_summary": bool(config.get("feishu_push_daily_summary", True)),
        }

    def test_feishu(self) -> dict:
        config = self.config()
        webhook = config["feishu_webhook_url"]
        if not webhook:
            return {"ok": False, "message": "请先配置飞书机器人 Webhook。"}
        text = (
            "OKX Quant Agent 飞书测试消息\n"
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "说明：如果你看到了这条消息，说明飞书推送链路已经接通。"
        )
        return self.send_text(webhook, text)

    def send_daily_summary(self, strategy_name: str, report: dict, summary: dict | None = None) -> dict:
        config = self.config()
        webhook = config["feishu_webhook_url"]
        if not webhook:
            return {"ok": False, "message": "未配置飞书机器人 Webhook。", "skipped": True}

        text = self._build_daily_summary_message(
            strategy_name=strategy_name,
            report=report or {},
            summary=summary or {},
            include_report=config["feishu_push_daily_report"],
            include_summary=config["feishu_push_daily_summary"],
        )
        if not text:
            return {"ok": False, "message": "飞书推送已跳过：日报与策略总结都未开启。", "skipped": True}
        return self.send_text(webhook, text)

    def send_text(self, webhook_url: str, text: str) -> dict:
        payload = {"msg_type": "text", "content": {"text": text}}
        request = Request(
            webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8", errors="ignore")
            parsed = json.loads(body or "{}")
            ok = str(parsed.get("code", "0")) == "0"
            return {
                "ok": ok,
                "message": "飞书测试消息发送成功。" if ok else parsed.get("msg", "飞书返回异常"),
                "response": parsed,
            }
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            return {"ok": False, "message": f"飞书请求失败 HTTP {exc.code}", "response": body}
        except URLError as exc:
            return {"ok": False, "message": f"飞书请求失败：{exc.reason}"}
        except Exception as exc:
            return {"ok": False, "message": f"飞书请求失败：{exc}"}

    def _build_daily_summary_message(
        self,
        strategy_name: str,
        report: dict,
        summary: dict,
        include_report: bool,
        include_summary: bool,
    ) -> str:
        lines = [f"OKX Quant Agent 每日推送", f"策略：{strategy_name or '--'}"]
        date_text = report.get("date") or summary.get("date") or datetime.now().strftime("%Y-%m-%d")
        lines.append(f"日期：{date_text}")

        if include_report:
            sections = report.get("sections") or []
            lines.append("")
            lines.append("【每日日报】")
            if sections:
                for section in sections[:4]:
                    title = str(section.get("title") or "未命名板块")
                    body = str(section.get("body") or "暂无内容").strip()
                    lines.append(f"{title}：{body}")
            else:
                lines.append("暂无日报内容。")

        if include_summary:
            lines.append("")
            lines.append("【策略总结】")
            lines.append(f"市场观点：{summary.get('market_view') or '--'}")
            lines.append(f"置信度：{summary.get('confidence') if summary.get('confidence') is not None else '--'}")
            lines.append(f"动作：{summary.get('action') or '--'}")
            lines.append(f"标的：{summary.get('symbol') or '--'}")
            lines.append(f"仓位建议：{summary.get('position_size') if summary.get('position_size') is not None else '--'}")
            reasons = summary.get("reason") or []
            if isinstance(reasons, list) and reasons:
                lines.append("原因：" + "；".join(str(item) for item in reasons[:4]))
            if summary.get("risk_note"):
                lines.append(f"风险提醒：{summary.get('risk_note')}")
            if summary.get("next_step"):
                lines.append(f"下一步：{summary.get('next_step')}")
            if summary.get("summary"):
                lines.append(f"摘要：{summary.get('summary')}")

        return "\n".join(lines).strip()
