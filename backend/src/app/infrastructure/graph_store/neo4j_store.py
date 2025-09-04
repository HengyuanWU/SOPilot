#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础设施：Neo4j 图存储实现

职责：
- 基于 core.kg_store.neo4j_client 提供的 Neo4jClient 封装 KGStore 接口
- 供域层 KGPipeline 直接依赖（不再依赖 modules.*）
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List

from .neo4j_client import Neo4jClient, create_neo4j_client
from ...domain.kg.store import KGStore


logger = logging.getLogger(__name__)


class Neo4jKGStore:
    """实现 KGStore 协议，委托给 Neo4jClient。"""

    def __init__(self, client: Neo4jClient):
        self.client = client

    def merge_node(self, node: Dict[str, Any]) -> bool:
        return self.client.merge_node(node)

    def merge_edge(self, edge: Dict[str, Any]) -> bool:
        return self.client.merge_edge(edge)

    def delete_edges_by_src(self, section_id: str) -> int:
        return self.client.delete_edges_by_src(section_id)

    def delete_edges_by_scope(self, scope: str) -> int:
        """按scope删除关系"""
        return self.client.delete_edges_by_scope(scope)

    def get_stats(self) -> Dict[str, int]:
        return self.client.get_graph_stats()


def create_neo4j_store(config: Optional[Dict[str, Any]] = None) -> Optional[Neo4jKGStore]:
    """
    从配置创建 Neo4jKGStore 实例。

    Args:
        config: 包含 neo4j 配置的字典，结构与 AppSettings.neo4j 对齐。

    Returns:
        Neo4jKGStore 或 None（配置缺失/连接失败）。
    """
    try:
        cfg_to_use: Dict[str, Any] = config or {}
        # 当未显式传入或缺少 neo4j 配置时，从 AppSettings 读取
        if not cfg_to_use.get("neo4j"):
            try:
                from ...core.settings import get_settings
                s = get_settings()
                neo = s.neo4j.model_dump(exclude_none=True)
                cfg_to_use = {"neo4j": neo} if neo else {}
            except Exception as _e:
                logger.warning(f"读取 AppSettings 失败，尝试直接使用传入配置: {_e}")

        client = create_neo4j_client(cfg_to_use)
        if client:
            logger.info("Neo4jKGStore 已创建")
            return Neo4jKGStore(client)
        return None
    except Exception as e:
        logger.error(f"创建 Neo4jKGStore 失败: {e}")
        return None


def fetch_section_graph(section_id: str) -> Optional[Dict[str, Any]]:
    """
    查询指定 section_id 的节点与边，返回标准结构。

    Returns:
        {
            "section_id": str,
            "nodes": List[Dict[str, Any]],
            "edges": List[Dict[str, Any]],
            "stats": {"total_nodes": int, "total_edges": int}
        } 或 None
    """
    try:
        store = create_neo4j_store()
        if not store:
            return None

        # 查询边（带全部属性）
        edges_query = (
            "MATCH ()-[r]->() WHERE r.src = $section_id "
            "RETURN properties(r) AS edge"
        )
        edge_rows: List[Dict[str, Any]] = store.client.execute_cypher(edges_query, {"section_id": section_id}) or []
        edges: List[Dict[str, Any]] = [row.get("edge", {}) for row in edge_rows if isinstance(row.get("edge"), dict)]

        if not edges:
            return {"section_id": section_id, "nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}

        # 依据边上的 source_id/target_id 查询节点属性
        nodes_query = (
            "MATCH ()-[r]->() WHERE r.src = $section_id "
            "WITH collect(DISTINCT r.source_id) + collect(DISTINCT r.target_id) AS ids "
            "UNWIND ids AS nid MATCH (n {id: nid}) "
            "RETURN DISTINCT properties(n) AS node"
        )
        node_rows: List[Dict[str, Any]] = store.client.execute_cypher(nodes_query, {"section_id": section_id}) or []
        nodes: List[Dict[str, Any]] = [row.get("node", {}) for row in node_rows if isinstance(row.get("node"), dict)]

        return {
            "section_id": section_id,
            "nodes": nodes,
            "edges": edges,
            "stats": {"total_nodes": len(nodes), "total_edges": len(edges)},
        }
    except Exception as e:
        logger.error(f"fetch_section_graph 失败: {e}")
        return None


def fetch_book_graph(book_id: str) -> Optional[Dict[str, Any]]:
    """
    查询指定 book_id 的整本书图谱，按scope查询。
    
    Args:
        book_id: 书籍ID，如 "book:python_basics:12345678"
        
    Returns:
        {
            "book_id": str,
            "nodes": List[Dict[str, Any]],
            "edges": List[Dict[str, Any]], 
            "stats": {"total_nodes": int, "total_edges": int}
        } 或 None
    """
    try:
        store = create_neo4j_store()
        if not store:
            return None

        scope = f"book:{book_id}" if not book_id.startswith("book:") else book_id
        
        # 查询边（带全部属性）
        edges_query = (
            "MATCH ()-[r]->() WHERE r.scope = $scope "
            "RETURN properties(r) AS edge"
        )
        edge_rows: List[Dict[str, Any]] = store.client.execute_cypher(edges_query, {"scope": scope}) or []
        edges: List[Dict[str, Any]] = [row.get("edge", {}) for row in edge_rows if isinstance(row.get("edge"), dict)]

        if not edges:
            return {"book_id": book_id, "nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}

        # 依据边上的 source_id/target_id 查询节点属性
        nodes_query = (
            "MATCH ()-[r]->() WHERE r.scope = $scope "
            "WITH collect(DISTINCT r.source_id) + collect(DISTINCT r.target_id) AS ids "
            "UNWIND ids AS nid MATCH (n {id: nid}) "
            "RETURN DISTINCT properties(n) AS node"
        )
        node_rows: List[Dict[str, Any]] = store.client.execute_cypher(nodes_query, {"scope": scope}) or []
        nodes: List[Dict[str, Any]] = [row.get("node", {}) for row in node_rows if isinstance(row.get("node"), dict)]

        return {
            "book_id": book_id,
            "nodes": nodes,
            "edges": edges,
            "stats": {"total_nodes": len(nodes), "total_edges": len(edges)},
        }
    except Exception as e:
        logger.error(f"fetch_book_graph 失败: {e}")
        return None

