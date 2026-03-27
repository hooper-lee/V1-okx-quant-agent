from __future__ import annotations

from datetime import datetime, timezone


class OKXCCXTClient:
    def __init__(self, settings, runtime_config_service=None) -> None:
        self.settings = settings
        self.runtime_config_service = runtime_config_service
        self._exchange = None
        self._exchange_fingerprint = None

    def _runtime_overrides(self) -> dict:
        if self.runtime_config_service is None:
            return {}
        return self.runtime_config_service.load()

    def has_private_auth(self) -> bool:
        overrides = self._runtime_overrides()
        return bool(
            (overrides.get("okx_api_key") or self.settings.okx_api_key)
            and (overrides.get("okx_api_secret") or self.settings.okx_api_secret)
            and (overrides.get("okx_passphrase") or self.settings.okx_passphrase)
        )

    def is_paper_mode(self) -> bool:
        overrides = self._runtime_overrides()
        return bool(overrides.get("okx_use_paper", self.settings.okx_use_paper))

    def available(self) -> bool:
        try:
            import ccxt  # noqa: F401
        except ImportError:
            return False
        return True

    def _to_ccxt_symbol(self, symbol: str) -> str:
        normalized = str(symbol or "").strip().upper()
        if normalized.endswith("-SWAP"):
            base, quote, _ = normalized.split("-")
            return f"{base}/{quote}:{quote}"
        if "-" in normalized:
            base, quote = normalized.split("-", 1)
            return f"{base}/{quote}"
        return normalized

    def _build_exchange(self):
        overrides = self._runtime_overrides()
        fingerprint = (
            overrides.get("okx_api_key") or self.settings.okx_api_key,
            overrides.get("okx_api_secret") or self.settings.okx_api_secret,
            overrides.get("okx_passphrase") or self.settings.okx_passphrase,
            bool(overrides.get("okx_use_paper", self.settings.okx_use_paper)),
        )
        if self._exchange is not None and self._exchange_fingerprint == fingerprint:
            return self._exchange
        import ccxt

        exchange = ccxt.okx(
            {
                "apiKey": overrides.get("okx_api_key") or self.settings.okx_api_key,
                "secret": overrides.get("okx_api_secret") or self.settings.okx_api_secret,
                "password": overrides.get("okx_passphrase") or self.settings.okx_passphrase,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",
                },
            }
        )
        exchange.set_sandbox_mode(self.is_paper_mode())
        self._exchange = exchange
        self._exchange_fingerprint = fingerprint
        return exchange

    def fetch_ticker(self, symbol: str) -> dict:
        exchange = self._build_exchange()
        ticker = exchange.fetch_ticker(self._to_ccxt_symbol(symbol))
        return {
            "symbol": symbol,
            "last": float(ticker.get("last", 0) or 0),
            "bid": float(ticker.get("bid", 0) or 0),
            "ask": float(ticker.get("ask", 0) or 0),
            "source": "okx-ccxt",
            "raw": ticker,
        }

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 50) -> list[dict]:
        exchange = self._build_exchange()
        rows = exchange.fetch_ohlcv(self._to_ccxt_symbol(symbol), timeframe=timeframe, limit=limit)
        candles = []
        for row in rows:
            candles.append(
                {
                    "timestamp": datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc).isoformat(),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )
        return candles

    def test_public_connection(self, symbol: str) -> dict:
        try:
            ticker = self.fetch_ticker(symbol)
            return {"ok": True, "message": "OKX 公共行情接口连接成功（ccxt）。", "ticker": ticker}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def test_private_connection(self) -> dict:
        if not self.has_private_auth():
            return {"ok": False, "message": "缺少 OKX 私有接口凭证，请先填写 API Key / Secret / Passphrase。"}
        try:
            account = self.get_account_balance()
            return {"ok": True, "message": "OKX 私有账户接口连接成功（ccxt）。", "accounts": [account]}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def get_account_balance(self) -> dict:
        exchange = self._build_exchange()
        balance = exchange.fetch_balance()
        usdt_total = float((balance.get("total") or {}).get("USDT", 0) or 0)
        usdt_free = float((balance.get("free") or {}).get("USDT", 0) or 0)
        assets = []
        for asset, total in (balance.get("total") or {}).items():
            if not total:
                continue
            assets.append(
                {
                    "asset": asset,
                    "equity": float(total or 0),
                    "available": float((balance.get("free") or {}).get(asset, 0) or 0),
                    "upl": 0.0,
                }
            )
        return {
            "source": "okx-ccxt",
            "mode": "paper" if self.is_paper_mode() else "live",
            "connection_state": "connected",
            "total_equity": usdt_total,
            "available_equity": usdt_free,
            "upl": 0.0,
            "assets": assets[:12],
            "raw": balance,
        }

    def get_positions(self) -> dict:
        exchange = self._build_exchange()
        positions = exchange.fetch_positions()
        items = []
        for item in positions:
            size = float(item.get("contracts", 0) or 0)
            if size == 0:
                continue
            items.append(
                {
                    "symbol": item.get("symbol", ""),
                    "side": item.get("side", ""),
                    "size": size,
                    "entry_price": float(item.get("entryPrice", 0) or 0),
                    "mark_price": float(item.get("markPrice", 0) or 0),
                    "upl": float(item.get("unrealizedPnl", 0) or 0),
                    "upl_ratio": float(item.get("percentage", 0) or 0) / 100 if item.get("percentage") is not None else 0.0,
                    "leverage": float(item.get("leverage", 0) or 0),
                    "margin_mode": item.get("marginMode", ""),
                }
            )
        return {
            "source": "okx-ccxt",
            "mode": "paper" if self.is_paper_mode() else "live",
            "connection_state": "connected",
            "items": items,
            "raw": positions,
        }

    def get_open_orders(self, symbol: str | None = None) -> dict:
        exchange = self._build_exchange()
        orders = exchange.fetch_open_orders(self._to_ccxt_symbol(symbol) if symbol else None)
        return {"source": "okx-ccxt", "items": orders, "raw": orders}

    def get_order_history(self, symbol: str | None = None, limit: int = 20) -> dict:
        exchange = self._build_exchange()
        orders = exchange.fetch_closed_orders(self._to_ccxt_symbol(symbol) if symbol else None, limit=limit)
        return {"source": "okx-ccxt", "items": orders, "raw": orders}

    def set_leverage(self, inst_id: str, leverage: float, margin_mode: str = "cross", pos_side: str = "") -> dict:
        exchange = self._build_exchange()
        result = exchange.set_leverage(float(leverage), self._to_ccxt_symbol(inst_id), params={"marginMode": margin_mode, "posSide": pos_side} if pos_side else {"marginMode": margin_mode})
        return {"result": result}

    def place_order(self, symbol: str, side: str, size: float, strategy_config: dict | None = None) -> dict:
        strategy_config = strategy_config or {}
        exchange = self._build_exchange()
        leverage = float(strategy_config.get("leverage", 1.0) or 1.0)
        margin_mode = str(strategy_config.get("margin_mode", "cross") or "cross")
        try:
            exchange.set_leverage(leverage, self._to_ccxt_symbol(symbol), params={"marginMode": margin_mode})
        except Exception:
            pass
        order = exchange.create_order(self._to_ccxt_symbol(symbol), "market", side, size)
        return {
            "status": "submitted",
            "exchange": "OKX",
            "symbol": symbol,
            "side": side,
            "size": size,
            "order_id": order.get("id", ""),
            "mode": "paper" if self.is_paper_mode() else "live",
            "margin_mode": margin_mode,
            "leverage": leverage,
            "pos_side": order.get("side", side),
            "instrument_type": "SWAP" if str(symbol).upper().endswith("-SWAP") else "SPOT",
            "raw": order,
        }
