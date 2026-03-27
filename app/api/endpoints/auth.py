from __future__ import annotations

import hashlib
import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.container import runtime_config_service
from app.core.config import settings

router = APIRouter()

AUTH_COOKIE_NAME = "okx_agent_auth"


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


def _configured_password() -> str:
    return str(runtime_config_service.get("app_password", "") or getattr(settings, "app_password", "") or "")


def _session_ttl_minutes() -> int:
    raw_value = runtime_config_service.get("app_session_ttl_minutes", 30)
    try:
        ttl = int(raw_value or 30)
    except (TypeError, ValueError):
        ttl = 30
    return max(1, min(ttl, 7 * 24 * 60))


def _cookie_signature(password: str, expires_at: int) -> str:
    return hashlib.sha256(f"{password}:okx-quant-agent:{expires_at}".encode("utf-8")).hexdigest()


def _cookie_value(password: str, expires_at: int) -> str:
    return f"{expires_at}:{_cookie_signature(password=password, expires_at=expires_at)}"


def is_request_authorized(cookie_value: str | None) -> bool:
    password = _configured_password()
    if not password:
        return True
    if not cookie_value:
        return False
    try:
        expires_text, signature = str(cookie_value).split(":", 1)
        expires_at = int(expires_text)
    except (ValueError, TypeError):
        return False
    if expires_at <= int(time.time()):
        return False
    return secrets.compare_digest(signature, _cookie_signature(password=password, expires_at=expires_at))


@router.get("/status")
def auth_status(request: Request) -> dict:
    password = _configured_password()
    return {
        "item": {
            "enabled": bool(password),
            "authenticated": is_request_authorized(request.cookies.get(AUTH_COOKIE_NAME)),
            "ttl_minutes": _session_ttl_minutes(),
        }
    }


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict:
    password = _configured_password()
    if not password:
        return {"item": {"enabled": False, "authenticated": True, "ttl_minutes": _session_ttl_minutes()}}
    if not secrets.compare_digest(payload.password, password):
        raise HTTPException(status_code=401, detail="密码错误")
    ttl_minutes = _session_ttl_minutes()
    expires_at = int(time.time()) + ttl_minutes * 60
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=_cookie_value(password=password, expires_at=expires_at),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=ttl_minutes * 60,
    )
    return {"item": {"enabled": True, "authenticated": True, "ttl_minutes": ttl_minutes}}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(AUTH_COOKIE_NAME)
    return {"item": {"authenticated": False}}
