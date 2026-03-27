from fastapi import APIRouter

from app.core.container import langchain_runtime, notification_service, okx_client, runtime_config_service
from app.schemas.runtime_config import RuntimeConfigUpdateRequest
 
router = APIRouter()


@router.get("")
def get_runtime_config() -> dict:
    return {"item": runtime_config_service.load()}


@router.put("")
def update_runtime_config(payload: RuntimeConfigUpdateRequest) -> dict:
    item = runtime_config_service.save(
        {
            "app_password": payload.app_password,
            "app_session_ttl_minutes": payload.app_session_ttl_minutes,
            "openai_api_key": payload.openai_api_key,
            "openai_model": payload.openai_model,
            "llm_model": payload.llm_model,
            "llm_temperature": payload.llm_temperature,
            "openai_base_url": payload.openai_base_url,
            "embeddings_enabled": payload.embeddings_enabled,
            "embeddings_use_shared_credentials": payload.embeddings_use_shared_credentials,
            "embeddings_api_key": payload.embeddings_api_key,
            "embeddings_base_url": payload.embeddings_base_url,
            "embeddings_model": payload.embeddings_model,
            "okx_api_key": payload.okx_api_key,
            "okx_api_secret": payload.okx_api_secret,
            "okx_passphrase": payload.okx_passphrase,
            "okx_rest_base": payload.okx_rest_base,
            "okx_use_paper": payload.okx_use_paper,
            "okx_adapter": payload.okx_adapter,
            "feishu_webhook_url": payload.feishu_webhook_url,
            "feishu_push_daily_report": payload.feishu_push_daily_report,
            "feishu_push_daily_summary": payload.feishu_push_daily_summary,
        }
    )
    langchain_runtime.reset_clients()
    return {"item": item}


@router.post("/test-llm")
def test_llm_connection() -> dict:
    return langchain_runtime.test_connection()


@router.post("/test-embeddings")
def test_embeddings_connection() -> dict:
    return langchain_runtime.test_embeddings()


@router.post("/test-okx")
def test_okx_connection() -> dict:
    return okx_client.test_connection()


@router.post("/test-okx-public")
def test_okx_public_connection() -> dict:
    return okx_client.test_public_connection()


@router.post("/test-okx-private")
def test_okx_private_connection() -> dict:
    return okx_client.test_private_connection()


@router.post("/okx-diagnostics")
def run_okx_diagnostics() -> dict:
    config = runtime_config_service.load()
    public_result = okx_client.test_public_connection()
    private_result = okx_client.test_private_connection()
    candidate_scan = okx_client.diagnose_candidates()
    return {
        "item": {
            "rest_base": config.get("okx_rest_base", "https://www.okx.com"),
            "adapter": config.get("okx_adapter", "native"),
            "mode": "paper" if config.get("okx_use_paper", True) else "live",
            "has_private_auth": okx_client.has_private_auth(),
            "public": public_result,
            "private": private_result,
            "recommended_rest_base": candidate_scan.get("recommended_rest_base"),
            "candidates": candidate_scan.get("candidates", []),
        }
    }


@router.post("/test-feishu")
def test_feishu_connection() -> dict:
    return notification_service.test_feishu()
