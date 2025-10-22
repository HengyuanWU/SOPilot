#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ID 与 RID 生成、查重（按IMPROOVE_GUIDE.md规范）
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

__all__ = ["IdGen"]


class IdGen:
    """幂等性ID生成器。
    
    - 节点 id = concept:{slug(name)}:{md5(topic|chapter|subchapter)[:6]}
    - 关系 rid = md5(type|source_id|target_id|scope)[:16]
    """

    def __init__(self, settings):
        """初始化ID生成器。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings

    def assign(self, linked: dict, section: dict) -> dict:
        """对链接后的概念和关系分配ID。
        
        Args:
            linked: 链接后的图谱数据，包含 concepts 和 relations
            section: 小节元数据，包含 section_id, book_topic, chapter_title, subchapter_title
            
        Returns:
            准备好的图谱数据，所有节点和关系都已分配ID
        """
        ready = {"concepts": [], "relations": []}
        
        # 为新概念生成ID
        context = f"{section['book_topic']}|{section['chapter_title']}|{section['subchapter_title']}"
        context_hash = hashlib.md5(context.encode()).hexdigest()[:6]
        
        for c in linked.get("concepts", []):
            if not c.get("existing_id"):
                # 新概念，生成ID
                slug = self._slugify(c["name"])
                c["id"] = f"concept:{slug}:{context_hash}"
            else:
                # 已有概念，使用existing_id
                c["id"] = c["existing_id"]
            
            # 补齐scope
            c["scope"] = section["section_id"]
            ready["concepts"].append(c)
        
        # 为关系生成RID
        concept_map = {c["name"]: c["id"] for c in ready["concepts"]}
        
        for r in linked.get("relations", []):
            src_id = concept_map.get(r["src_name"])
            tgt_id = concept_map.get(r["tgt_name"])
            
            if not src_id or not tgt_id:
                # 找不到源或目标节点，跳过
                continue
            
            r["source_id"] = src_id
            r["target_id"] = tgt_id
            r["src"] = section["section_id"]
            r["scope"] = section["section_id"]
            
            # 生成RID
            rid_str = f"{r['type']}|{src_id}|{tgt_id}|{r['scope']}"
            r["rid"] = hashlib.md5(rid_str.encode()).hexdigest()[:16]
            
            ready["relations"].append(r)
        
        return ready

    @staticmethod
    def _slugify(text: str) -> str:
        """将文本转为slug格式。
        
        Args:
            text: 原始文本
            
        Returns:
            slug格式的文本
        """
        # 转小写
        text = text.lower()
        # 移除特殊字符，保留字母、数字、中文
        text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
        # 替换空格为下划线
        text = re.sub(r"\s+", "_", text)
        # 移除首尾下划线
        text = text.strip("_")
        # 限制长度
        if len(text) > 50:
            text = text[:50]
        return text
