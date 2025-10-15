#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG API 端点（按IMPROOVE_GUIDE.md规范）
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.settings import AppSettings, get_settings
from ...domain.kg.service import KGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kg")


class KGSectionBuildRequest(BaseModel):
    """KG小节构建请求（严格按IMPROOVE_GUIDE.md要求）"""

    section_id: str
    book_topic: str
    chapter_title: str
    subchapter_title: str
    chunks: list[dict[str, str]]  # [{"id": "doc1#p3", "text": "..."}, ...]


class KGSectionBuildResponse(BaseModel):
    """KG小节构建响应"""

    section_id: str
    book_id: str
    stats: dict[str, Any]


@router.post("/sections:build", response_model=KGSectionBuildResponse)
async def build_kg_section(
    request: KGSectionBuildRequest, settings: AppSettings = Depends(get_settings)
):
    """
    构建小节知识图谱（严格按IMPROOVE_GUIDE.md要求）

    触发KG流水线：Builder → Normalizer → Linker → Idempotent → Store → Merger

    Args:
        request: 小节构建请求，包含section_id, book_topic, chapter_title等
        settings: 应用配置

    Returns:
        构建结果，包含section_id, book_id和统计信息
    """
    try:
        # 验证chunks
        if not request.chunks:
            raise HTTPException(status_code=400, detail="chunks不能为空")

        # 构建section数据（按照IMPROOVE_GUIDE.md第5.1节格式）
        section_data = {
            "section_id": request.section_id,
            "book_topic": request.book_topic,
            "chapter_title": request.chapter_title,
            "subchapter_title": request.subchapter_title,
            "chunks": request.chunks,
        }

        # 初始化KG服务
        kg_service = KGService(settings)

        # 执行KG构建
        result = kg_service.build_section(section_data)

        # 返回标准响应
        return KGSectionBuildResponse(
            section_id=result["section_id"],
            book_id=result["book_id"],
            stats=result.get("stats", {}),
        )

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.exception(f"小节构建内部错误: {e}")
        raise HTTPException(
            status_code=500, detail=f"小节构建内部错误: {str(e)}"
        ) from e


@router.get("/books/{book_id}")
async def get_book_graph(
    book_id: str, settings: AppSettings = Depends(get_settings)
):
    """
    获取整书知识图谱（前端优先使用，按IMPROOVE_GUIDE.md要求）

    Args:
        book_id: 书籍ID，格式如 book:topic:hash
        settings: 应用配置

    Returns:
        书籍知识图谱，包含nodes和edges数组（如果没有数据返回空数组）
    """
    try:
        # 初始化KG服务
        kg_service = KGService(settings)

        # 获取书籍图谱
        book_graph = kg_service.get_book_graph(book_id)

        # 返回空数据而不是404（遵循RESTful最佳实践）
        if not book_graph or (
            not book_graph.get("nodes") and not book_graph.get("edges")
        ):
            logger.info(f"书籍图谱为空: {book_id}")
            return {"nodes": [], "edges": []}

        return {"nodes": book_graph.get("nodes", []), "edges": book_graph.get("edges", [])}

    except Exception as e:
        logger.exception(f"获取书籍图谱失败 {book_id}: {e}")
        raise HTTPException(
            status_code=500, detail="获取书籍图谱失败"
        ) from e


@router.get("/sections/{section_id}")
async def get_section_graph(
    section_id: str, settings: AppSettings = Depends(get_settings)
):
    """
    获取小节知识图谱（降级使用，按IMPROOVE_GUIDE.md要求）

    Args:
        section_id: 小节ID
        settings: 应用配置

    Returns:
        小节知识图谱，包含nodes和edges数组（如果没有数据返回空数组）
    """
    try:
        # 初始化KG服务
        kg_service = KGService(settings)

        # 获取小节图谱
        section_graph = kg_service.get_section_graph(section_id)

        # 返回空数据而不是404（与get_book_graph保持一致）
        if not section_graph or (
            not section_graph.get("nodes") and not section_graph.get("edges")
        ):
            logger.info(f"小节图谱为空: {section_id}")
            return {"nodes": [], "edges": []}

        return {
            "nodes": section_graph.get("nodes", []),
            "edges": section_graph.get("edges", []),
        }

    except Exception as e:
        logger.exception(f"获取小节图谱失败 {section_id}: {e}")
        raise HTTPException(
            status_code=500, detail="获取小节图谱失败"
        ) from e

