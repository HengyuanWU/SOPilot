#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j 统一网关（通过 neomodel）
按IMPROOVE_GUIDE.md规范
"""

from __future__ import annotations

from typing import Iterable

from neomodel import db

__all__ = ["Neo4jStore"]


class Neo4jStore:
    """提供最小访问面以供其他层调用；内部全部走 neomodel 的 db。"""

    @staticmethod
    def run_cypher(query: str, params: dict | None = None) -> list[dict]:
        """执行 Cypher 查询并返回字典列表。
        
        Args:
            query: Cypher 查询语句
            params: 查询参数字典
            
        Returns:
            结果记录的字典列表
        """
        results, meta = db.cypher_query(query, params or {})
        
        # 处理meta格式：可能是字典列表或字符串列表
        if not meta:
            return []
            
        # 如果meta是字符串列表（列名），直接使用
        if isinstance(meta[0], str):
            keys = meta
        # 如果meta是字典列表，提取name字段
        else:
            keys = [m.get("name", m) for m in meta]
        
        out = []
        for row in results:
            obj = {}
            for k, v in zip(keys, row):
                obj[k] = v
            out.append(obj)
        return out

    @staticmethod
    def run_tx(queries: Iterable[tuple[str, dict]]):
        """在单个事务中执行多个查询。
        
        Args:
            queries: (query, params) 元组的可迭代对象
        """
        with db.transaction:
            for q, p in queries:
                db.cypher_query(q, p)



