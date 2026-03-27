from __future__ import annotations

from pathlib import Path


class PromptTemplateService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[dict]:
        templates = []
        for path in sorted(self.base_dir.glob("*/system.txt")):
            templates.append(
                {
                    "name": path.parent.name,
                    "path": str(path),
                }
            )
        return templates

    def get_template(self, name: str) -> dict:
        path = self._resolve(name)
        return {"name": name, "content": path.read_text(encoding="utf-8")}

    def save_template(self, name: str, content: str) -> dict:
        path = self._resolve(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"name": name, "content": content}

    def render(self, name: str) -> str:
        path = self._resolve(name)
        return path.read_text(encoding="utf-8")

    def _resolve(self, name: str) -> Path:
        return self.base_dir / name / "system.txt"
