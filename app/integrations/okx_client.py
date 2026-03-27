from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional
from urllib import error, parse, request

from app.integrations.okx_ccxt_client import OKXCCXTClient


class OKXClient:
    def __init__(self, settings, runtime_config_service=None) -> None:
        self.settings = settings
        self.runtime_config_service = runtime_config_service
        self._ccxt_client = OKXCCXTClient(settings=settings, runtime_config_service=runtime_config_service)

    def _runtime_overrides(self) -> dict:
        if self.runtime_config_service is None:
            return {}
        return self.runtime_config_service.load()

    def has_private_auth(self) -> bool:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.has_private_auth()
        overrides = self._runtime_overrides()
        return bool(
            (overrides.get("okx_api_key") or self.settings.okx_api_key)
            and (overrides.get("okx_api_secret") or self.settings.okx_api_secret)
            and (overrides.get("okx_passphrase") or self.settings.okx_passphrase)
        )

    def rest_base(self) -> str:
        overrides = self._runtime_overrides()
        return overrides.get("okx_rest_base", self.settings.okx_rest_base)

    def adapter_mode(self) -> str:
        overrides = self._runtime_overrides()
        return str(overrides.get("okx_adapter", "native") or "native").strip().lower()

    def candidate_rest_bases(self) -> list[str]:
        if self.adapter_mode() == "ccxt":
            return ["ccxt-adapter"]
        overrides = self._runtime_overrides()
        configured = overrides.get("okx_rest_base", self.settings.okx_rest_base)
        candidates = [configured, "https://www.okx.com", "https://us.okx.com"]
        ordered: list[str] = []
        for item in candidates:
            base = str(item or "").strip().rstrip("/")
            if base and base not in ordered:
                ordered.append(base)
        return ordered

    def is_paper_mode(self) -> bool:
        overrides = self._runtime_overrides()
        return bool(overrides.get("okx_use_paper", self.settings.okx_use_paper))

    def fetch_ticker(self, symbol: str) -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.fetch_ticker(symbol)
        response = self.get("/api/v5/market/ticker", params={"instId": symbol})
        ticker = response.get("data", [{}])[0]
        return {
            "symbol": symbol,
            "last": float(ticker.get("last", 0)),
            "bid": float(ticker.get("bidPx", 0)),
            "ask": float(ticker.get("askPx", 0)),
            "source": "okx-live",
            "raw": ticker,
        }

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 50) -> list[dict]:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.fetch_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        response = self.get(
            "/api/v5/market/candles",
            params={"instId": symbol, "bar": self._to_okx_bar(timeframe), "limit": limit},
        )
        rows = response.get("data", [])
        candles = []
        for row in reversed(rows):
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

    def _to_okx_bar(self, timeframe: str) -> str:
        mapping = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D"}
        return mapping.get(timeframe, "1H")

    def get(self, path: str, params: Optional[dict] = None, auth: bool = False) -> dict:
        params = params or {}
        query = f"?{parse.urlencode(params)}" if params else ""
        return self._request("GET", f"{path}{query}", auth=auth)

    def post(self, path: str, payload: dict, auth: bool = True) -> dict:
        return self._request("POST", path, payload=payload, auth=auth)

    def _request(self, method: str, path: str, payload: Optional[dict] = None, auth: bool = False) -> dict:
        last_exc: Optional[Exception] = None
        for base in self.candidate_rest_bases():
            try:
                return self._request_once(method=method, path=path, payload=payload, auth=auth, base_url=base)
            except Exception as exc:
                last_exc = exc
                if not self._should_try_next_base(exc):
                    raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No OKX endpoint candidates available.")

    def _request_once(
        self,
        method: str,
        path: str,
        payload: Optional[dict] = None,
        auth: bool = False,
        base_url: Optional[str] = None,
    ) -> dict:
        overrides = self._runtime_overrides()
        url = f"{(base_url or self.rest_base()).rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8") if payload else None
        headers = {"Content-Type": "application/json"}
        if auth:
            timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            body_text = body.decode("utf-8") if body else ""
            prehash = f"{timestamp}{method.upper()}{path}{body_text}"
            signature = base64.b64encode(
                hmac.new(
                    (overrides.get("okx_api_secret") or self.settings.okx_api_secret).encode("utf-8"),
                    prehash.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")
            headers.update(
                {
                    "OK-ACCESS-KEY": overrides.get("okx_api_key") or self.settings.okx_api_key,
                    "OK-ACCESS-SIGN": signature,
                    "OK-ACCESS-TIMESTAMP": timestamp,
                    "OK-ACCESS-PASSPHRASE": overrides.get("okx_passphrase") or self.settings.okx_passphrase,
                }
            )
            if self.is_paper_mode():
                headers["x-simulated-trading"] = "1"

        req = request.Request(url=url, data=body, headers=headers, method=method.upper())
        with request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _should_try_next_base(self, exc: Exception) -> bool:
        if isinstance(exc, error.HTTPError):
            return exc.code in {403, 404}
        if isinstance(exc, error.URLError):
            return True
        return False

    def _format_error(self, exc: Exception, auth: bool = False) -> str:
        if isinstance(exc, error.HTTPError):
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            if exc.code == 403:
                return "HTTP 403 Forbidden：当前网络、地区或访问域名可能被 OKX 拒绝。若公共行情都 403，通常不是 API Key 问题。"
            if exc.code == 401:
                return "HTTP 401 Unauthorized：鉴权失败，请检查 OKX_API_KEY / OKX_API_SECRET / OKX_PASSPHRASE 是否正确。"
            if exc.code == 400 and auth:
                return f"HTTP 400 Bad Request：私有接口请求格式或签名可能有问题。{body}".strip()
            return f"HTTP {exc.code}：{body or exc.reason}"
        if isinstance(exc, error.URLError):
            return f"网络连接失败：{exc.reason}"
        return str(exc)

    def test_public_connection(self, symbol: str = "BTC-USDT-SWAP") -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.test_public_connection(symbol)
        try:
            ticker = self.fetch_ticker(symbol)
            return {"ok": True, "message": "OKX 公共行情接口连接成功。", "ticker": ticker}
        except Exception as exc:
            return {"ok": False, "message": self._format_error(exc, auth=False)}

    def test_private_connection(self) -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.test_private_connection()
        if not self.has_private_auth():
            return {"ok": False, "message": "缺少 OKX 私有接口凭证，请先填写 API Key / Secret / Passphrase。"}
        try:
            response = self.get("/api/v5/account/balance", auth=True)
            items = response.get("data", [])
            return {"ok": True, "message": "OKX 私有账户接口连接成功。", "accounts": items[:1]}
        except Exception as exc:
            return {"ok": False, "message": self._format_error(exc, auth=True)}

    def get_account_balance(self) -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.get_account_balance()
        return self.get("/api/v5/account/balance", auth=True)

    def get_positions(self, inst_type: str = "SWAP") -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.get_positions()
        return self.get("/api/v5/account/positions", params={"instType": inst_type}, auth=True)

    def get_open_orders(self, inst_type: str = "SWAP") -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.get_open_orders()
        return self.get("/api/v5/trade/orders-pending", params={"instType": inst_type}, auth=True)

    def get_order_history(self, inst_type: str = "SWAP", limit: int = 20) -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.get_order_history(limit=limit)
        return self.get("/api/v5/trade/orders-history", params={"instType": inst_type, "limit": limit}, auth=True)

    def set_leverage(self, inst_id: str, leverage: float, margin_mode: str = "cross", pos_side: str = "") -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.set_leverage(inst_id=inst_id, leverage=leverage, margin_mode=margin_mode, pos_side=pos_side)
        payload = {
            "instId": inst_id,
            "lever": str(leverage),
            "mgnMode": margin_mode,
        }
        if pos_side:
            payload["posSide"] = pos_side
        return self.post("/api/v5/account/set-leverage", payload=payload, auth=True)

    def order_precheck(self, payload: dict) -> dict:
        if self.adapter_mode() == "ccxt":
            return {"code": "0", "msg": "ccxt adapter skips native precheck", "data": [payload]}
        return self.post("/api/v5/trade/order-precheck", payload=payload, auth=True)

    def place_order(self, symbol: str, side: str, size: float, strategy_config: dict | None = None) -> dict:
        if self.adapter_mode() == "ccxt":
            return self._ccxt_client.place_order(symbol=symbol, side=side, size=size, strategy_config=strategy_config)
        raise NotImplementedError("Native adapter uses executor order flow.")

    def test_connection(self, symbol: str = "BTC-USDT-SWAP") -> dict:
        public_result = self.test_public_connection(symbol=symbol)
        private_result = self.test_private_connection()
        return {"ok": public_result.get("ok") and private_result.get("ok"), "public": public_result, "private": private_result}

    def diagnose_candidates(self, symbol: str = "BTC-USDT-SWAP") -> dict:
        if self.adapter_mode() == "ccxt":
            public_result = self.test_public_connection(symbol=symbol)
            private_result = self.test_private_connection()
            return {
                "candidates": [
                    {
                        "rest_base": "ccxt-adapter",
                        "public": public_result,
                        "private": private_result,
                        "recommended": bool(public_result.get("ok")) and (private_result.get("ok") or not self.has_private_auth()),
                    }
                ],
                "recommended_rest_base": "ccxt-adapter",
            }
        candidates = []
        for base in self.candidate_rest_bases():
            public_result = self._probe_base(base, symbol=symbol, auth=False)
            private_result = self._probe_base(base, symbol=symbol, auth=True) if self.has_private_auth() else {
                "ok": False,
                "message": "缺少 OKX 私有接口凭证，请先填写 API Key / Secret / Passphrase。",
            }
            candidates.append(
                {
                    "rest_base": base,
                    "public": public_result,
                    "private": private_result,
                    "recommended": bool(public_result.get("ok")) and (private_result.get("ok") or not self.has_private_auth()),
                }
            )
        recommended = next((item["rest_base"] for item in candidates if item["recommended"]), self.rest_base())
        return {"candidates": candidates, "recommended_rest_base": recommended}

    def _probe_base(self, base: str, symbol: str, auth: bool) -> dict:
        try:
            if auth:
                response = self._request_once("GET", "/api/v5/account/balance", auth=True, base_url=base)
                return {"ok": True, "message": "OKX 私有账户接口连接成功。", "accounts": (response.get("data") or [])[:1]}
            response = self._request_once("GET", f"/api/v5/market/ticker?{parse.urlencode({'instId': symbol})}", auth=False, base_url=base)
            ticker = response.get("data", [{}])[0]
            return {"ok": True, "message": "OKX 公共行情接口连接成功。", "ticker": ticker}
        except Exception as exc:
            return {"ok": False, "message": self._format_error(exc, auth=auth)}
