from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    topic: str = Field(..., description="主题或任务描述")
    language: str = Field("中文", description="生成语言")
    chapter_count: int = Field(8, ge=1, le=20, description="章节数（教材工作流适用）")
    workflow_id: str = Field("textbook", description="工作流ID，默认为textbook以保持向后兼容")
    workflow_params: Optional[Dict[str, Any]] = Field(None, description="工作流特定参数")


class RunCreated(BaseModel):
    id: str
    status: str


class RunStatus(BaseModel):
    id: str
    status: str
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    updated_at: Optional[int] = None

