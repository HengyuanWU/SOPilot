#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务层（按IMPROOVE_GUIDE.md规范）
供 API 调用
"""

from __future__ import annotations

from app.infrastructure.graph_store.neo4j_store import fetch_book_graph, fetch_section_graph

from .pipeline import KGPipeline

__all__ = ["KGService"]


class KGService:
    """知识图谱服务层。"""

    def __init__(self, settings):
        """初始化服务层。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings
        self.pipeline = KGPipeline(settings)

    def build_section(self, section: dict) -> dict:
        """构建小节图谱。
        
        Args:
            section: 小节数据，格式见 KGPipeline.run
            
        Returns:
            构建结果
        """
        return self.pipeline.run(section)

    def get_book_graph(self, book_id: str) -> dict:
        """获取整书图谱。
        
        Args:
            book_id: 书籍ID
            
        Returns:
            图谱数据：{"nodes": [...], "edges": [...]}
        """
        # 使用基础设施层的fetch_book_graph函数（已处理book_id前缀）
        result = fetch_book_graph(book_id)
        
        if not result:
            return {"nodes": [], "edges": []}
        
        return {"nodes": result.get("nodes", []), "edges": result.get("edges", [])}

    def get_section_graph(self, section_id: str) -> dict:
        """获取小节图谱。
        
        Args:
            section_id: 小节ID
            
        Returns:
            图谱数据：{"nodes": [...], "edges": [...]}
        """
        # 使用基础设施层的fetch_section_graph函数
        result = fetch_section_graph(section_id)
        
        if not result:
            return {"nodes": [], "edges": []}
        
        return {"nodes": result.get("nodes", []), "edges": result.get("edges", [])}
