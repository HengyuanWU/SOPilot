from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    topic: str = Field(..., description="教材主题")
    language: str = Field("中文", description="生成语言")
    chapter_count: int = Field(ge=1, le=20, description="章节数")


class RunCreated(BaseModel):
    id: str
    status: str


class RunStatus(BaseModel):
    id: str
    status: str
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    updated_at: Optional[int] = None

