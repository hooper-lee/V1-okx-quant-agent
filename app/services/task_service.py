from __future__ import annotations

from datetime import datetime
import threading
from typing import Awaitable, Callable
from uuid import uuid4
import asyncio


class TaskService:
    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}

    def create_task(self, label: str, runner: Callable[[], Awaitable[dict] | dict]) -> dict:
        task_id = uuid4().hex
        item = {
            "id": task_id,
            "label": label,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "started_at": "",
            "finished_at": "",
            "result": None,
            "error": "",
        }
        self._tasks[task_id] = item
        thread = threading.Thread(target=self._run_sync, args=(task_id, runner), daemon=True)
        thread.start()
        return item

    def _run_sync(self, task_id: str, runner: Callable[[], Awaitable[dict] | dict]) -> None:
        asyncio.run(self._run(task_id=task_id, runner=runner))

    async def _run(self, task_id: str, runner: Callable[[], Awaitable[dict] | dict]) -> None:
        item = self._tasks[task_id]
        item["status"] = "running"
        item["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            result = runner()
            if asyncio.iscoroutine(result):
                result = await result
            item["result"] = result
            item["status"] = "completed"
        except Exception as exc:
            item["error"] = str(exc)
            item["status"] = "failed"
        finally:
            item["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._trim()

    def get(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    def _trim(self) -> None:
        if len(self._tasks) <= 50:
            return
        ordered = sorted(self._tasks.values(), key=lambda item: item["created_at"])
        for item in ordered[:-50]:
            self._tasks.pop(item["id"], None)
