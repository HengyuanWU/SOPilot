#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体链接器（按IMPROOVE_GUIDE.md规范）
- 先规则：名称规范化后做完全/别名匹配
- 再语义：通过 Embedding API 计算相似度
- 不安装本地 sentence-transformers，不做本地向量推理
"""

from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz

from app.infrastructure.graph_store.neomodel_store import Neo4jStore

__all__ = ["EntityLinker"]


class EntityLinker:
    """实体链接器，用于复用已有概念节点。"""

    def __init__(self, settings):
        """初始化实体链接器。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings
        self.threshold = settings.KG_LINK_MIN_SIM
        self.fuzzy_threshold = 85  # 模糊匹配阈值

    def link(self, draft: dict) -> dict:
        """链接概念到已有节点。
        
        Args:
            draft: 规范化后的图谱数据
            
        Returns:
            链接后的图谱数据，包含 existing_id 字段
        """
        # 预加载已有概念
        existing_concepts = self._load_existing_concepts()
        
        out = []
        for c in draft.get("concepts", []):
            # 1. 完全匹配
            found = self._exact_match(c["name"], existing_concepts)
            if found:
                c["existing_id"] = found["id"]
                out.append(c)
                continue
            
            # 2. 别名匹配
            found = self._alias_match(c["name"], existing_concepts)
            if found:
                c["existing_id"] = found["id"]
                out.append(c)
                continue
            
            # 3. 模糊匹配（使用rapidfuzz）
            found = self._fuzzy_match(c["name"], existing_concepts)
            if found:
                c["existing_id"] = found["id"]
                out.append(c)
                continue
            
            # 4. TODO: 语义匹配（Embedding API）
            # 当前版本暂不实现语义匹配，留待后续完善
            # found = self._semantic_match(c["name"], existing_concepts)
            # if found:
            #     c["existing_id"] = found["id"]
            
            out.append(c)
        
        draft["concepts"] = out
        return draft

    def _load_existing_concepts(self) -> list[dict]:
        """从Neo4j加载已有概念（使用neomodel ORM）。
        
        Returns:
            已有概念列表
        """
        from .models import Concept
        
        try:
            # 使用 neomodel ORM 查询
            concepts = Concept.nodes.all()[:10000]
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "aliases": c.aliases or [],
                }
                for c in concepts
            ]
        except Exception:
            # 图谱为空或连接失败，返回空列表
            return []

    @staticmethod
    def _exact_match(name: str, existing: list[dict]) -> Optional[dict]:
        """完全匹配。
        
        Args:
            name: 待匹配的名称
            existing: 已有概念列表
            
        Returns:
            匹配的概念，如果没有返回None
        """
        for c in existing:
            if c["name"] == name:
                return c
        return None

    @staticmethod
    def _alias_match(name: str, existing: list[dict]) -> Optional[dict]:
        """别名匹配。
        
        Args:
            name: 待匹配的名称
            existing: 已有概念列表
            
        Returns:
            匹配的概念，如果没有返回None
        """
        for c in existing:
            aliases = c.get("aliases") or []
            if name in aliases:
                return c
        return None

    def _fuzzy_match(self, name: str, existing: list[dict]) -> Optional[dict]:
        """模糊匹配（使用rapidfuzz）。
        
        Args:
            name: 待匹配的名称
            existing: 已有概念列表
            
        Returns:
            匹配的概念，如果没有返回None
        """
        best_match = None
        best_score = 0
        
        for c in existing:
            # 计算与name的相似度
            score = fuzz.ratio(name, c["name"])
            if score > best_score:
                best_score = score
                best_match = c
            
            # 也检查别名
            for alias in (c.get("aliases") or []):
                score = fuzz.ratio(name, alias)
                if score > best_score:
                    best_score = score
                    best_match = c
        
        if best_score >= self.fuzzy_threshold:
            return best_match
        
        return None
