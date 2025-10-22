#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j Schema 安装（约束/索引）
按IMPROOVE_GUIDE.md规范
"""

from __future__ import annotations
import logging

from app.infrastructure.graph_store.neomodel_store import Neo4jStore

logger = logging.getLogger(__name__)

__all__ = ["install_schema"]

# 节点约束/索引（固定）
NODE_CONSTRAINTS = [
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id   IF NOT EXISTS FOR (n:Chunk)   REQUIRE n.id IS UNIQUE",
    "CREATE INDEX     concept_scope  IF NOT EXISTS FOR (n:Concept) ON (n.scope)",
    "CREATE INDEX     chunk_scope    IF NOT EXISTS FOR (n:Chunk) ON (n.scope)",
]

# 关系类型列表
RELATION_TYPES = [
    "DEFINES",
    "EXPLAINS", 
    "REQUIRES",
    "SIMILAR_TO",
    "CONTRASTS_WITH",
    "IMPLEMENTS",
    "PART_OF",
]

# 关系索引（为每种关系类型创建索引）
REL_INDEXES = []
for rel_type in RELATION_TYPES:
    REL_INDEXES.extend([
        f"CREATE INDEX {rel_type.lower()}_scope IF NOT EXISTS FOR ()-[r:{rel_type}]-() ON (r.scope)",
        f"CREATE INDEX {rel_type.lower()}_rid   IF NOT EXISTS FOR ()-[r:{rel_type}]-() ON (r.rid)",
    ])


def _check_constraint_exists(name: str) -> bool:
    """检查约束是否已存在"""
    try:
        query = "SHOW CONSTRAINTS YIELD name WHERE name = $name RETURN count(*) > 0 as exists"
        result = Neo4jStore.run_cypher(query, {"name": name})
        return result[0]['exists'] if result else False
    except Exception:
        # 如果查询失败（可能是旧版本Neo4j），返回False让它尝试创建
        return False


def _check_index_exists(name: str) -> bool:
    """检查索引是否已存在"""
    try:
        query = "SHOW INDEXES YIELD name WHERE name = $name RETURN count(*) > 0 as exists"
        result = Neo4jStore.run_cypher(query, {"name": name})
        return result[0]['exists'] if result else False
    except Exception:
        # 如果查询失败（可能是旧版本Neo4j），返回False让它尝试创建
        return False


def install_schema() -> None:
    """一次性执行，重复调用安全。仅创建不存在的约束/索引。"""
    constraints_to_create = []
    indexes_to_create = []
    
    # 检查节点约束
    if not _check_constraint_exists("concept_id"):
        constraints_to_create.append(
            "CREATE CONSTRAINT concept_id FOR (n:Concept) REQUIRE n.id IS UNIQUE"
        )
    if not _check_constraint_exists("chunk_id"):
        constraints_to_create.append(
            "CREATE CONSTRAINT chunk_id FOR (n:Chunk) REQUIRE n.id IS UNIQUE"
        )
    
    # 检查节点索引
    if not _check_index_exists("concept_scope"):
        indexes_to_create.append(
            "CREATE INDEX concept_scope FOR (n:Concept) ON (n.scope)"
        )
    if not _check_index_exists("chunk_scope"):
        indexes_to_create.append(
            "CREATE INDEX chunk_scope FOR (n:Chunk) ON (n.scope)"
        )
    
    # 检查关系索引
    for rel_type in RELATION_TYPES:
        scope_idx = f"{rel_type.lower()}_scope"
        rid_idx = f"{rel_type.lower()}_rid"
        
        if not _check_index_exists(scope_idx):
            indexes_to_create.append(
                f"CREATE INDEX {scope_idx} FOR ()-[r:{rel_type}]-() ON (r.scope)"
            )
        if not _check_index_exists(rid_idx):
            indexes_to_create.append(
                f"CREATE INDEX {rid_idx} FOR ()-[r:{rel_type}]-() ON (r.rid)"
            )
    
    # 执行创建
    created_count = 0
    for cypher in constraints_to_create + indexes_to_create:
        Neo4jStore.run_cypher(cypher)
        created_count += 1
    
    if created_count > 0:
        logger.info(f"创建了 {created_count} 个新的约束/索引")
    else:
        logger.debug("所有约束和索引已存在，跳过创建")



