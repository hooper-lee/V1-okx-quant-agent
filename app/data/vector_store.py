from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class ExperienceVectorStore:
    def __init__(self, settings, runtime) -> None:
        self.settings = settings
        self.runtime = runtime
        self._store_path = Path(self.settings.memory_store_path)
        self._seed_items: list[dict] = [
            {
                "topic": "trend-following",
                "content": "When short-term and mid-term averages align, allow momentum strategies to lead.",
            },
            {
                "topic": "risk",
                "content": "Reduce position size in volatility spikes and before macro catalysts.",
            },
        ]
        self._items: list[dict] = []
        self._vector_store = None
        self._seeded = False
        self._load_items()

    def _load_items(self) -> None:
        loaded_items: list[dict] = []
        if self._store_path.exists():
            try:
                payload = json.loads(self._store_path.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    loaded_items = [self._normalize_item(item) for item in payload]
            except (OSError, ValueError, TypeError):
                loaded_items = []

        seen_keys = set()
        merged_items: list[dict] = []
        for item in [*self._seed_items, *loaded_items]:
            normalized = self._normalize_item(item)
            key = (normalized["topic"], normalized["content"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged_items.append(normalized)

        self._items = merged_items
        self._persist_items()

    def _normalize_item(self, item: dict) -> dict:
        timestamp = item.get("created_at") or item.get("timestamp") or datetime.now().isoformat()
        return {
            "topic": str(item.get("topic", "memory")).strip() or "memory",
            "content": str(item.get("content", "")).strip(),
            "created_at": str(timestamp),
        }

    def _persist_items(self) -> None:
        try:
            self._store_path.write_text(
                json.dumps(self._items, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return

    def _ensure_store(self):
        if self._vector_store is not None:
            return self._vector_store

        embeddings = self.runtime.build_embeddings()
        if embeddings is None:
            return None
        try:
            from langchain_chroma import Chroma
            from langchain_core.documents import Document
        except ImportError:
            return None

        persist_directory = Path(self.settings.chroma_persist_directory)
        persist_directory.mkdir(parents=True, exist_ok=True)
        self._vector_store = Chroma(
            collection_name="okx_quant_experience",
            embedding_function=embeddings,
            persist_directory=str(persist_directory),
        )

        if not self._seeded:
            try:
                self._vector_store.add_documents(
                    [Document(page_content=item["content"], metadata={"topic": item["topic"]}) for item in self._items]
                )
                self._seeded = True
            except Exception:
                self._vector_store = None
        return self._vector_store

    def search(self, query: str, limit: int = 4) -> list[dict]:
        vector_store = self._ensure_store()
        if vector_store is not None:
            try:
                docs = vector_store.similarity_search(query, k=limit)
                return [{"topic": doc.metadata.get("topic", "memory"), "content": doc.page_content} for doc in docs]
            except Exception:
                pass

        query_lower = query.lower()
        matches = [
            item
            for item in self._items
            if query_lower in item["topic"].lower() or query_lower in item["content"].lower()
        ]
        if matches:
            return matches[:limit]
        return sorted(self._items, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]

    def add_memory(self, topic: str, content: str) -> None:
        item = self._normalize_item({"topic": topic, "content": content})
        self._items.append(item)
        self._persist_items()
        vector_store = self._ensure_store()
        if vector_store is not None:
            try:
                from langchain_core.documents import Document

                vector_store.add_documents(
                    [
                        Document(
                            page_content=item["content"],
                            metadata={"topic": item["topic"], "created_at": item["created_at"]},
                        )
                    ]
                )
            except Exception:
                return

    def list_by_topic_prefix(self, prefix: str, limit: int = 10) -> list[dict]:
        matches = [item for item in self._items if str(item.get("topic", "")).startswith(prefix)]
        matches.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return matches[:limit]
