from __future__ import annotations

import json
from pathlib import Path


class RuntimeConfigService:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.write_text("{}", encoding="utf-8")

    def load(self) -> dict:
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, payload: dict) -> dict:
        current = self.load()
        current.update(payload)
        self.config_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        return current

    def get(self, key: str, default=None):
        return self.load().get(key, default)
