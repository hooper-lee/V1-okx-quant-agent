from __future__ import annotations

from datetime import datetime, timezone

from app.integrations.okx_client import OKXClient


class OKXExecutor:
    def __init__(self, settings, runtime_config_service=None) -> None:
        self.settings = settings
        self.client = OKXClient(settings=settings, runtime_config_service=runtime_config_service)

    def place_order(self, symbol: str, side: str, size: float, strategy_config: dict | None = None) -> dict:
        strategy_config = strategy_config or {}
        is_swap = symbol.upper().endswith("-SWAP")
        margin_mode = str(strategy_config.get("margin_mode", "cross") or "cross")
        leverage = float(strategy_config.get("leverage", 1.0) or 1.0)
        position_mode = str(strategy_config.get("position_mode", "net") or "net")
        pos_side = ""
        if is_swap and position_mode == "long_short":
            pos_side = "long" if side == "buy" else "short"
        if self.settings.use_live_services and self.client.has_private_auth() and self.client.adapter_mode() == "ccxt":
            try:
                return self.client.place_order(symbol=symbol, side=side, size=size, strategy_config=strategy_config)
            except Exception as exc:
                return {
                    "status": "error",
                    "exchange": "OKX",
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "order_id": "",
                    "mode": "paper" if self.settings.okx_use_paper else "live",
                    "margin_mode": margin_mode if is_swap else "cash",
                    "leverage": leverage,
                    "pos_side": pos_side,
                    "instrument_type": "SWAP" if is_swap else "SPOT",
                    "error": str(exc),
                }
        if self.settings.use_live_services and self.client.has_private_auth():
            try:
                td_mode = "cash"
                order_payload = {
                    "instId": symbol,
                    "side": side,
                    "ordType": "market",
                    "sz": str(size),
                }
                if is_swap:
                    td_mode = margin_mode
                    order_payload["tdMode"] = td_mode
                    if pos_side:
                        order_payload["posSide"] = pos_side
                    try:
                        self.client.set_leverage(inst_id=symbol, leverage=leverage, margin_mode=margin_mode, pos_side=pos_side)
                    except Exception:
                        pass
                    try:
                        precheck = self.client.order_precheck(order_payload)
                    except Exception as precheck_exc:
                        return {
                            "status": "error",
                            "exchange": "OKX",
                            "symbol": symbol,
                            "side": side,
                            "size": size,
                            "order_id": "",
                            "mode": "paper" if self.settings.okx_use_paper else "live",
                            "error": f"order precheck failed: {precheck_exc}",
                            "order_payload": order_payload,
                        }
                    order_payload["precheck"] = precheck
                else:
                    order_payload["tdMode"] = td_mode
                response = self.client.post(
                    "/api/v5/trade/order",
                    payload={key: value for key, value in order_payload.items() if key != "precheck"},
                    auth=True,
                )
                data = response.get("data", [{}])[0]
                return {
                    "status": "submitted",
                    "exchange": "OKX",
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "order_id": data.get("ordId", ""),
                    "mode": "paper" if self.settings.okx_use_paper else "live",
                    "margin_mode": td_mode,
                    "leverage": leverage,
                    "pos_side": pos_side,
                    "instrument_type": "SWAP" if is_swap else "SPOT",
                    "order_payload": order_payload,
                    "raw": response,
                }
            except Exception as exc:
                return {
                    "status": "error",
                    "exchange": "OKX",
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "order_id": "",
                    "mode": "paper" if self.settings.okx_use_paper else "live",
                    "margin_mode": margin_mode if is_swap else "cash",
                    "leverage": leverage,
                    "pos_side": pos_side,
                    "instrument_type": "SWAP" if is_swap else "SPOT",
                    "error": str(exc),
                }

        return {
            "status": "submitted",
            "exchange": "OKX",
            "symbol": symbol,
            "side": side,
            "size": size,
            "order_id": f"SIM-{int(datetime.now(timezone.utc).timestamp())}",
            "mode": "paper",
            "margin_mode": margin_mode if is_swap else "cash",
            "leverage": leverage,
            "pos_side": pos_side,
            "instrument_type": "SWAP" if is_swap else "SPOT",
            "realized_pnl": 0.0,
        }

    def get_account_overview(self) -> dict:
        if self.settings.use_live_services and self.client.has_private_auth():
            try:
                if self.client.adapter_mode() == "ccxt":
                    return self.client.get_account_balance()
                response = self.client.get_account_balance()
                account = (response.get("data") or [{}])[0]
                details = account.get("details") or []
                total_equity = float(account.get("totalEq", 0) or 0)
                available_equity = float(account.get("adjEq", 0) or 0)
                return {
                    "source": "okx-live",
                    "mode": "paper" if self.client.is_paper_mode() else "live",
                    "connection_state": "connected",
                    "total_equity": total_equity,
                    "available_equity": available_equity,
                    "upl": float(account.get("upl", 0) or 0),
                    "assets": [
                        {
                            "asset": item.get("ccy", ""),
                            "equity": float(item.get("eq", 0) or 0),
                            "available": float(item.get("availEq", item.get("availBal", 0)) or 0),
                            "upl": float(item.get("upl", 0) or 0),
                        }
                        for item in details[:12]
                    ],
                    "raw": response,
                }
            except Exception as exc:
                return {**self._demo_account_overview(), "source": "demo-fallback", "connection_state": "fallback", "error": str(exc)}
        return self._demo_account_overview()

    def list_positions(self) -> dict:
        if self.settings.use_live_services and self.client.has_private_auth():
            try:
                if self.client.adapter_mode() == "ccxt":
                    return self.client.get_positions()
                response = self.client.get_positions()
                items = response.get("data") or []
                return {
                    "source": "okx-live",
                    "mode": "paper" if self.client.is_paper_mode() else "live",
                    "connection_state": "connected",
                    "items": [
                        {
                            "symbol": item.get("instId", ""),
                            "side": item.get("posSide") or ("long" if float(item.get("pos", 0) or 0) >= 0 else "short"),
                            "size": float(item.get("pos", 0) or 0),
                            "entry_price": float(item.get("avgPx", 0) or 0),
                            "mark_price": float(item.get("markPx", 0) or 0),
                            "upl": float(item.get("upl", 0) or 0),
                            "upl_ratio": float(item.get("uplRatio", 0) or 0),
                        }
                        for item in items
                    ],
                    "raw": response,
                }
            except Exception as exc:
                return {**self._demo_positions(), "source": "demo-fallback", "connection_state": "fallback", "error": str(exc)}
        return self._demo_positions()

    def list_orders(self) -> dict:
        if self.settings.use_live_services and self.client.has_private_auth():
            try:
                if self.client.adapter_mode() == "ccxt":
                    pending = self.client.get_open_orders()
                    history = self.client.get_order_history(limit=20)
                    return {
                        "source": "okx-ccxt",
                        "mode": "paper" if self.client.is_paper_mode() else "live",
                        "connection_state": "connected",
                        "pending": [self._normalize_ccxt_order(item, status="pending") for item in (pending.get("items") or [])],
                        "history": [self._normalize_ccxt_order(item) for item in (history.get("items") or [])],
                        "raw": {"pending": pending, "history": history},
                    }
                pending = self.client.get_open_orders()
                history = self.client.get_order_history(limit=20)
                return {
                    "source": "okx-live",
                    "mode": "paper" if self.client.is_paper_mode() else "live",
                    "connection_state": "connected",
                    "pending": [self._normalize_order(item, status="pending") for item in (pending.get("data") or [])],
                    "history": [self._normalize_order(item) for item in (history.get("data") or [])],
                    "raw": {"pending": pending, "history": history},
                }
            except Exception as exc:
                return {**self._demo_orders(), "source": "demo-fallback", "connection_state": "fallback", "error": str(exc)}
        return self._demo_orders()

    def _normalize_order(self, item: dict, status: str | None = None) -> dict:
        return {
            "order_id": item.get("ordId", ""),
            "symbol": item.get("instId", ""),
            "side": item.get("side", ""),
            "type": item.get("ordType", ""),
            "size": float(item.get("sz", 0) or 0),
            "filled_size": float(item.get("accFillSz", 0) or 0),
            "price": float(item.get("px", 0) or 0),
            "avg_price": float(item.get("avgPx", 0) or 0),
            "status": status or item.get("state", ""),
            "created_at": item.get("cTime", ""),
            "updated_at": item.get("uTime", ""),
        }

    def _normalize_ccxt_order(self, item: dict, status: str | None = None) -> dict:
        return {
            "order_id": item.get("id", ""),
            "symbol": item.get("symbol", ""),
            "side": item.get("side", ""),
            "type": item.get("type", ""),
            "size": float(item.get("amount", 0) or 0),
            "filled_size": float(item.get("filled", 0) or 0),
            "price": float(item.get("price", 0) or 0),
            "avg_price": float(item.get("average", 0) or 0),
            "status": status or item.get("status", ""),
            "created_at": item.get("datetime", "") or str(item.get("timestamp", "")),
            "updated_at": item.get("lastTradeTimestamp", "") or str(item.get("timestamp", "")),
        }

    def _demo_account_overview(self) -> dict:
        return {
            "source": "demo",
            "mode": "paper",
            "connection_state": "simulated",
            "total_equity": 12543.62,
            "available_equity": 9781.14,
            "upl": 286.41,
            "margin_ratio": 0.231,
            "leveraged_notional": 8420.5,
            "assets": [
                {"asset": "USDT", "equity": 9781.14, "available": 9320.45, "upl": 0.0},
                {"asset": "BTC", "equity": 1736.88, "available": 1204.55, "upl": 182.37},
                {"asset": "ETH", "equity": 712.45, "available": 504.12, "upl": 74.04},
                {"asset": "SOL", "equity": 313.15, "available": 255.0, "upl": 30.0},
            ],
        }

    def _demo_positions(self) -> dict:
        return {
            "source": "demo",
            "mode": "paper",
            "connection_state": "simulated",
            "items": [
                {"symbol": "BTC-USDT-SWAP", "side": "long", "size": 0.08, "entry_price": 85120.0, "mark_price": 85980.0, "upl": 68.8, "upl_ratio": 0.0101, "leverage": 3, "margin_mode": "cross"},
                {"symbol": "ETH-USDT-SWAP", "side": "long", "size": 1.75, "entry_price": 2040.0, "mark_price": 2095.0, "upl": 96.25, "upl_ratio": 0.0269, "leverage": 2, "margin_mode": "cross"},
                {"symbol": "SOL-USDT-SWAP", "side": "short", "size": 12.0, "entry_price": 142.8, "mark_price": 139.4, "upl": 40.8, "upl_ratio": 0.0238, "leverage": 2, "margin_mode": "isolated"},
            ],
        }

    def _demo_orders(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "source": "demo",
            "mode": "paper",
            "connection_state": "simulated",
            "pending": [
                {"order_id": "SIM-PENDING-1", "symbol": "BTC-USDT-SWAP", "side": "buy", "type": "limit", "size": 0.015, "filled_size": 0.0, "price": 85200.0, "avg_price": 0.0, "status": "pending", "created_at": now.isoformat(), "updated_at": now.isoformat()},
                {"order_id": "SIM-PENDING-2", "symbol": "SOL-USDT-SWAP", "side": "sell", "type": "limit", "size": 5.0, "filled_size": 0.0, "price": 141.6, "avg_price": 0.0, "status": "pending", "created_at": now.isoformat(), "updated_at": now.isoformat()},
            ],
            "history": [
                {"order_id": "SIM-HIST-1", "symbol": "BTC-USDT-SWAP", "side": "buy", "type": "market", "size": 0.03, "filled_size": 0.03, "price": 0.0, "avg_price": 84980.0, "status": "filled", "created_at": now.isoformat(), "updated_at": now.isoformat()},
                {"order_id": "SIM-HIST-2", "symbol": "ETH-USDT-SWAP", "side": "sell", "type": "market", "size": 0.8, "filled_size": 0.8, "price": 0.0, "avg_price": 2088.0, "status": "filled", "created_at": now.isoformat(), "updated_at": now.isoformat()},
                {"order_id": "SIM-HIST-3", "symbol": "SOL-USDT-SWAP", "side": "sell", "type": "market", "size": 10.0, "filled_size": 10.0, "price": 0.0, "avg_price": 143.2, "status": "filled", "created_at": now.isoformat(), "updated_at": now.isoformat()},
            ],
        }
