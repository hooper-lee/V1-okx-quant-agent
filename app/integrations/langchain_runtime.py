from __future__ import annotations

import json
import re
from typing import Any, Optional


class LangChainRuntime:
    def __init__(self, settings, runtime_config_service=None) -> None:
        self.settings = settings
        self.runtime_config_service = runtime_config_service
        self._llm = None
        self._embeddings = None
        self._last_error = ""

    def reset_clients(self) -> None:
        self._llm = None
        self._embeddings = None
        self._last_error = ""

    def has_llm_credentials(self) -> bool:
        overrides = self._runtime_overrides()
        return bool(overrides.get("openai_api_key") or self.settings.openai_api_key)

    def has_embeddings_credentials(self) -> bool:
        overrides = self._runtime_overrides()
        if overrides.get("embeddings_enabled") is False:
            return False
        if overrides.get("embeddings_use_shared_credentials", True):
            return self.has_llm_credentials()
        return bool(overrides.get("embeddings_api_key"))

    def _runtime_overrides(self) -> dict:
        if self.runtime_config_service is None:
            return {}
        return self.runtime_config_service.load()

    def _build_llm(self):
        if self._llm is not None:
            return self._llm
        if not self.has_llm_credentials():
            self._last_error = "缺少 OPENAI_API_KEY。"
            return None
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            self._last_error = "缺少 langchain_openai 依赖。"
            return None

        overrides = self._runtime_overrides()
        kwargs: dict[str, Any] = {
            "model": overrides.get("llm_model", self.settings.llm_model),
            "temperature": overrides.get("llm_temperature", self.settings.llm_temperature),
            "api_key": overrides.get("openai_api_key") or self.settings.openai_api_key or None,
            "timeout": 60,
            "max_retries": 1,
        }
        base_url = overrides.get("openai_base_url", self.settings.openai_base_url)
        if base_url:
            kwargs["base_url"] = base_url
        try:
            self._llm = ChatOpenAI(**kwargs)
        except Exception as exc:
            self._last_error = f"初始化 LLM 失败：{exc}"
            self._llm = None
            return None
        return self._llm

    def build_embeddings(self):
        if self._embeddings is not None:
            return self._embeddings
        overrides = self._runtime_overrides()
        embeddings_enabled = overrides.get("embeddings_enabled")
        if embeddings_enabled is False:
            self._last_error = "Embeddings 未开启。"
            return None
        if not self.has_embeddings_credentials():
            self._last_error = "缺少 Embeddings 所需的 API Key。"
            return None
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            self._last_error = "缺少 langchain_openai 依赖。"
            return None

        model_name = overrides.get("embeddings_model") or overrides.get("openai_model") or self.settings.embeddings_model
        if not model_name:
            self._last_error = "缺少 Embeddings 模型配置。"
            return None
        use_shared_credentials = overrides.get("embeddings_use_shared_credentials", True)
        api_key = (
            overrides.get("openai_api_key") or self.settings.openai_api_key or None
            if use_shared_credentials
            else overrides.get("embeddings_api_key") or None
        )
        base_url = (
            overrides.get("openai_base_url", self.settings.openai_base_url)
            if use_shared_credentials
            else overrides.get("embeddings_base_url") or ""
        )
        kwargs: dict[str, Any] = {
            "model": model_name,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url
        try:
            self._embeddings = OpenAIEmbeddings(**kwargs)
        except Exception as exc:
            self._last_error = f"初始化 Embeddings 失败：{exc}"
            self._embeddings = None
            return None
        return self._embeddings

    def invoke_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        llm = self._build_llm()
        if llm is None:
            return None
        try:
            response = llm.invoke([("system", system_prompt), ("human", user_prompt)])
        except Exception as exc:
            self._last_error = str(exc)
            return None
        return getattr(response, "content", None) or str(response)

    def invoke_json(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        llm = self._build_llm()
        if llm is None:
            return None
        try:
            structured_llm = llm.bind(response_format={"type": "json_object"})
            response = structured_llm.invoke([("system", system_prompt), ("human", user_prompt)])
            content = getattr(response, "content", None) or str(response)
            if isinstance(content, list):
                content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
            return self._parse_json_content(content)
        except Exception as exc:
            primary_error = str(exc)
            try:
                response = llm.invoke([("system", system_prompt), ("human", user_prompt)])
                content = getattr(response, "content", None) or str(response)
                if isinstance(content, list):
                    content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
                parsed = self._parse_json_content(content)
                if parsed is not None:
                    return parsed
            except Exception as fallback_exc:
                self._last_error = f"{primary_error} | fallback: {fallback_exc}"
                return None
            self._last_error = primary_error
            return None

    def _parse_json_content(self, content: Any) -> Optional[dict]:
        if content is None:
            raise ValueError("模型返回空内容，无法解析 JSON。")
        text = str(content).strip()
        if not text:
            raise ValueError("模型返回空字符串，无法解析 JSON。")

        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            pass

        extracted = self._extract_json_block(text)
        if extracted:
            parsed = json.loads(extracted)
            return parsed if isinstance(parsed, dict) else {"value": parsed}

        raise ValueError(f"无法从模型输出中提取 JSON：{text[:240]}")

    def _extract_json_block(self, text: str) -> Optional[str]:
        decoder = json.JSONDecoder()
        for start_index, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                _, end_index = decoder.raw_decode(text[start_index:])
                return text[start_index : start_index + end_index]
            except json.JSONDecodeError:
                continue
        return None

    def test_connection(self) -> dict:
        self.reset_clients()
        reply = self.invoke_text(
            system_prompt="You are a healthcheck assistant. Respond with the single word OK.",
            user_prompt="Return OK only.",
        )
        if reply:
            return {"ok": True, "message": reply}
        return {"ok": False, "message": self._last_error or "LLM runtime unavailable or credentials invalid."}

    def test_embeddings(self) -> dict:
        self._embeddings = None
        self._last_error = ""
        embeddings = self.build_embeddings()
        if embeddings is None:
            return {"ok": False, "message": self._last_error or "Embeddings runtime unavailable or credentials invalid."}
        try:
            vector = embeddings.embed_query("healthcheck")
        except Exception as exc:
            self._last_error = str(exc)
            return {"ok": False, "message": self._last_error}
        return {"ok": True, "message": f"Embeddings 连接成功，维度 {len(vector)}"}
