from pydantic import BaseModel, Field


class NewsSourceConfigUpdateRequest(BaseModel):
    sources: list[dict] = Field(default_factory=list)
