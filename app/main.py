from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.container import automation_service
from app.api.endpoints.auth import AUTH_COOKIE_NAME, is_request_authorized

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="OKX Quant Agent",
    version="0.1.0",
    description="A LangChain-inspired OKX quantitative trading system skeleton.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.middleware("http")
async def password_gate(request: Request, call_next):
    open_paths = {
        "/health",
        "/api/v1/auth/status",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
    }
    path = request.url.path
    if path in open_paths:
        return await call_next(request)
    if path.startswith("/api/v1"):
        if not is_request_authorized(request.cookies.get(AUTH_COOKIE_NAME)):
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=401, content={"detail": "AUTH_REQUIRED", "scope": "app"})
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "okx-quant-agent"}


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.on_event("startup")
async def startup_automation() -> None:
    await automation_service.start()


@app.on_event("shutdown")
async def shutdown_automation() -> None:
    await automation_service.stop()
