from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.container import task_service

router = APIRouter()


@router.get("/{task_id}")
def get_task(task_id: str) -> dict:
    item = task_service.get(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"item": item}
