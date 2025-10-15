#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整书合并器（按IMPROOVE_GUIDE.md规范）
- 生成 book_id = book:{slug(topic)}:{md5(topic)[:8]}
- 删除旧 scope=book_id 的全部关系
- 汇总 Section 关系 → 写入 Book Scope（语义边，按 (type, source, target) 聚合）
"""

from __future__ import annotations

import hashlib

from app.infrastructure.graph_store.neomodel_store import Neo4jStore

from .idempotent import IdGen

__all__ = ["BookMerger"]

# 关系类型枚举
RELATION_TYPES = [
    "DEFINES",
    "EXPLAINS",
    "REQUIRES",
    "SIMILAR_TO",
    "CONTRASTS_WITH",
    "IMPLEMENTS",
    "PART_OF",
]


class BookMerger:
    """整书级别的图谱合并器。"""

    def __init__(self, settings):
        """初始化合并器。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings
        self.idgen = IdGen(settings)
        self.use_apoc = getattr(settings, "NEO4J_USE_APOC", False)
    
    def merge_book(self, topic: str) -> str:
        """合并整书图谱。
        
        Args:
            topic: 书籍主题
            
        Returns:
            book_id
        """
        # 生成book_id
        slug = self.idgen._slugify(topic)
        topic_hash = hashlib.md5(topic.encode()).hexdigest()[:8]
        book_id = f"book:{slug}:{topic_hash}"
        
        # 删除旧的book级关系
        self._delete_book_edges(book_id)
        
        # 汇总并写入book级关系
        self._aggregate_book_relations(book_id)
        
        return book_id

    def _delete_book_edges(self, book_id: str) -> None:
        """删除book的旧边。
        
        Args:
            book_id: 书籍ID
        """
        cypher = "MATCH ()-[r]-() WHERE r.scope = $scope DELETE r"
        Neo4jStore.run_cypher(cypher, {"scope": book_id})

    def _aggregate_book_relations(self, book_id: str) -> None:
        """汇总section关系为book关系。
        
        Args:
            book_id: 书籍ID
        """
        if self.use_apoc:
            # 使用APOC版本
            self._aggregate_with_apoc(book_id)
        else:
            # 不使用APOC版本
            self._aggregate_without_apoc(book_id)

    def _aggregate_with_apoc(self, book_id: str) -> None:
        """使用APOC聚合关系。
        
        Args:
            book_id: 书籍ID
        """
        cypher_template = """
        MATCH (s)-[r:%s]-(t) WHERE r.src IS NOT NULL AND r.src <> '__book_merge__'
        WITH DISTINCT type(r) AS typ, s.id AS sid, t.id AS tid
        WITH typ, sid, tid, $scope AS scope
        WITH typ, sid, tid, scope, toLower(typ) + '|' + sid + '|' + tid + '|' + scope AS sig
        WITH typ, sid, tid, scope, right(toHex(apoc.util.md5(sig)),16) AS rid
        MATCH (ss {id:sid}), (tt {id:tid})
        MERGE (ss)-[e:%s {rid:rid}]->(tt)
        SET e.type=typ, e.src='__book_merge__', e.scope=scope, 
            e.confidence=1.0, e.weight=1.0, 
            e.created_at=coalesce(e.created_at, datetime())
        """
        
        for typ in RELATION_TYPES:
            cypher = cypher_template % (typ, typ)
            try:
                Neo4jStore.run_cypher(cypher, {"scope": book_id})
            except Exception:
                # APOC不可用，回退到非APOC版本
                self.use_apoc = False
                self._aggregate_without_apoc(book_id)
                break

    def _aggregate_without_apoc(self, book_id: str) -> None:
        """不使用APOC聚合关系。
        
        Args:
            book_id: 书籍ID
        """
        # 查询所有section级关系（排除已经是book级的关系）
        cypher_query = """
        MATCH (s)-[r]-(t) 
        WHERE r.src IS NOT NULL AND r.src <> '__book_merge__'
        RETURN DISTINCT type(r) AS typ, s.id AS sid, t.id AS tid
        """
        
        results = Neo4jStore.run_cypher(cypher_query)
        
        # 按(typ, sid, tid)去重并生成rid
        unique_rels = {}
        for row in results:
            key = (row["typ"], row["sid"], row["tid"])
            if key not in unique_rels:
                # 生成rid
                rid_str = f"{row['typ']}|{row['sid']}|{row['tid']}|{book_id}"
                rid = hashlib.md5(rid_str.encode()).hexdigest()[:16]
                unique_rels[key] = {
                    "typ": row["typ"],
                    "sid": row["sid"],
                    "tid": row["tid"],
                    "rid": rid,
                }
        
        # 批量创建book级关系
        for rel in unique_rels.values():
            self._create_book_relation(rel, book_id)

    def _create_book_relation(self, rel: dict, book_id: str) -> None:
        """创建单个book级关系。
        
        Args:
            rel: 关系数据
            book_id: 书籍ID
        """
        # 动态构建Cypher（关系类型作为标签）
        cypher = f"""
        MATCH (ss {{id:$sid}}), (tt {{id:$tid}})
        MERGE (ss)-[e:{rel['typ']} {{rid:$rid}}]->(tt)
        SET e.type=$typ, e.src='__book_merge__', e.scope=$scope,
            e.confidence=1.0, e.weight=1.0,
            e.created_at=coalesce(e.created_at, datetime())
        """
        
        params = {
            "sid": rel["sid"],
            "tid": rel["tid"],
            "rid": rel["rid"],
            "typ": rel["typ"],
            "scope": book_id,
        }
        
        Neo4jStore.run_cypher(cypher, params)
