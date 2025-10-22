#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
存储层（按IMPROOVE_GUIDE.md规范）
- 通过 neomodel 的 db 执行
- 必须批量事务（KG_TX_BATCH_SIZE）
- 删除旧 Section 边 → MERGE 节点 → MERGE 关系（以 rid 幂等）
"""

from __future__ import annotations

from itertools import islice
from typing import Iterable

from app.infrastructure.graph_store.neomodel_store import Neo4jStore

__all__ = ["KGStore"]


class KGStore:
    """使用 neomodel 完成小节级写入（先删旧边 → 节点 MERGE → 关系 MERGE）。"""

    def __init__(self, settings):
        """初始化存储层。
        
        Args:
            settings: 应用配置对象
        """
        # 确保 neomodel 连接已正确设置（防止多进程/线程环境下连接丢失）
        from app.infrastructure.graph_store.neomodel_conn import init_neo4j
        init_neo4j(settings)
        
        self.batch = settings.KG_TX_BATCH_SIZE
        self.stats = {"nodes": 0, "edges": 0}
    
    def write_section(self, ready: dict, section_id: str) -> None:
        """写入小节级图谱数据。
        
        Args:
            ready: 准备好的图谱数据，包含 concepts 和 relations
            section_id: 小节ID
        """
        self._delete_section_edges(section_id)
        self._merge_concepts_batched(ready.get("concepts", []))
        self._merge_evidence_chunks(ready.get("concepts", []))
        self._merge_relations_batched(ready.get("relations", []))

    def _delete_section_edges(self, section_id: str) -> None:
        """删除小节的旧边。
        
        Args:
            section_id: 小节ID
        """
        cypher = "MATCH ()-[r]-() WHERE r.scope = $scope DELETE r"
        Neo4jStore.run_cypher(cypher, {"scope": section_id})

    def _merge_concepts_batched(self, concepts: list[dict]) -> None:
        """批量合并概念节点。
        
        Args:
            concepts: 概念列表
        """
        for chunk in _chunked(concepts, self.batch):
            # 使用Cypher MERGE来确保节点被创建或更新
            queries = []
            for c in chunk:
                cypher = """
                MERGE (n:Concept {id: $id})
                SET n.name = $name,
                    n.type = 'Concept',
                    n.aliases = $aliases,
                    n.desc = $desc,
                    n.updated_at = datetime(),
                    n.created_at = COALESCE(n.created_at, datetime())
                """
                params = {
                    "id": c["id"],
                    "name": c["name"],
                    "aliases": c.get("aliases", []),
                    "desc": c.get("desc", "")[:2048],
                }
                queries.append((cypher, params))
                self.stats["nodes"] += 1
            
            # 批量执行
            Neo4jStore.run_tx(queries)

    def _merge_evidence_chunks(self, concepts: list[dict]) -> None:
        """批量合并证据Chunk节点。
        
        Args:
            concepts: 概念列表（包含 mentions 字段）
        """
        all_mentions = []
        for c in concepts:
            all_mentions.extend(c.get("mentions", []))
        
        ids = sorted(set(all_mentions))
        
        for chunk in _chunked(ids, self.batch):
            queries = []
            for cid in chunk:
                if not cid:
                    continue
                cypher = """
                MERGE (n:Chunk {id: $id})
                SET n.name = $name,
                    n.type = 'Chunk',
                    n.updated_at = datetime(),
                    n.created_at = COALESCE(n.created_at, datetime())
                """
                params = {"id": cid, "name": cid}
                queries.append((cypher, params))
                self.stats["nodes"] += 1
            
            if queries:
                Neo4jStore.run_tx(queries)

    def _merge_relations_batched(self, rels: list[dict]) -> None:
        """批量合并关系。
        
        Args:
            rels: 关系列表
        """
        for batch in _chunked(rels, self.batch):
            # 为每个批次构建查询列表
            queries = []
            for r in batch:
                cypher = (
                    "MATCH (s {id:$sid}), (t {id:$tid}) "
                    "MERGE (s)-[e:%s {rid:$rid}]->(t) "
                    "SET e.type=$type, e.src=$src, e.scope=$scope, e.confidence=$confidence, "
                    "    e.weight=coalesce($weight,1.0), e.created_at=coalesce(e.created_at, datetime()), e.evidence=$evidence"
                ) % r["type"]
                
                params = {
                    "sid": r["source_id"],
                    "tid": r["target_id"],
                    "rid": r["rid"],
                    "type": r["type"],
                    "src": r["src"],
                    "scope": r["scope"],
                    "confidence": float(r.get("confidence", 1.0)),
                    "weight": r.get("weight"),
                    "evidence": r.get("evidence"),
                }
                queries.append((cypher, params))
                self.stats["edges"] += 1
            
            # 在事务中执行批次
            Neo4jStore.run_tx(queries)


def _chunked(iterable: Iterable, size: int):
    """将可迭代对象分块。
    
    Args:
        iterable: 可迭代对象
        size: 每块大小
        
    Yields:
        分块后的列表
    """
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            return
        yield batch
