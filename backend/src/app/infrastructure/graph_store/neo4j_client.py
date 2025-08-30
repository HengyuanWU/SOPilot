#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j 客户端（基础设施层）
完全内联实现，移除对旧 core 路径的依赖。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase, Driver
    from neo4j.exceptions import ServiceUnavailable, AuthError
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    Driver = None  # type: ignore
    ServiceUnavailable = Exception  # type: ignore
    AuthError = Exception  # type: ignore


logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        if GraphDatabase is None:
            raise ImportError("neo4j 包未安装。请运行: pip install neo4j")
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver: Optional[Driver] = None

    def connect(self) -> bool:
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )
            with self.driver.session(database=self.database) as session:
                _ = session.run("RETURN 1 as test").single()["test"]
                return True
        except (ServiceUnavailable, AuthError, Exception) as e:  # noqa: BLE001
            logger.error(f"Neo4j 连接失败: {e}")
            return False

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def merge_node(self, node: Dict[str, Any]) -> bool:
        if not self.driver:
            return False
        try:
            with self.driver.session(database=self.database) as session:
                node_type = node.get("type") or "Node"
                labels = {
                    "chapter": ":ChapterNode",
                    "subchapter": ":SubchapterNode",
                    "concept": ":ConceptNode",
                }.get(str(node_type).lower(), ":Node")
                cypher = f"""
                MERGE (n{labels} {{id: $id}})
                SET n += $properties
                SET n.updated_at = datetime()
                RETURN n.id as node_id
                """
                props = dict(node)
                if "created_at" not in props:
                    from datetime import datetime as _dt

                    props["created_at"] = _dt.utcnow().isoformat()
                _ = session.run(cypher, {"id": node["id"], "properties": props}).single()
                return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"合并节点失败: {e}")
            return False

    def merge_edge(self, edge: Dict[str, Any]) -> bool:
        if not self.driver:
            return False
        try:
            with self.driver.session(database=self.database) as session:
                edge_type_raw = str(edge.get("type", "")).strip()
                edge_type = self._sanitize_rel_type(edge_type_raw)
                
                # 使用rid做唯一匹配（如果提供了rid）
                rid = edge.get("rid")
                if rid:
                    cypher = f"""
                    MATCH (source {{id: $source_id}})
                    MATCH (target {{id: $target_id}})
                    MERGE (source)-[r:{edge_type} {{rid: $rid}}]->(target)
                    SET r += $properties
                    SET r.updated_at = datetime()
                    RETURN r.id as edge_id
                    """
                    params = {
                        "source_id": edge["source_id"],
                        "target_id": edge["target_id"],
                        "rid": rid,
                        "properties": edge,
                    }
                else:
                    # 兼容旧逻辑：不使用rid
                    cypher = f"""
                    MATCH (source {{id: $source_id}})
                    MATCH (target {{id: $target_id}})
                    MERGE (source)-[r:{edge_type}]->(target)
                    SET r += $properties
                    SET r.updated_at = datetime()
                    RETURN r.id as edge_id
                    """
                    params = {
                        "source_id": edge["source_id"],
                        "target_id": edge["target_id"],
                        "properties": edge,
                    }
                
                props = dict(edge)
                if edge_type_raw:
                    props["type_label"] = edge_type_raw
                if "id" not in props:
                    props["id"] = f"{edge_type}:{edge.get('source_id')}->{edge.get('target_id')}"
                if "created_at" not in props:
                    from datetime import datetime as _dt

                    props["created_at"] = _dt.utcnow().isoformat()
                
                params["properties"] = props
                _ = session.run(cypher, params).single()
                return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"合并边失败: {e}")
            return False

    def _sanitize_rel_type(self, raw: str) -> str:
        """将任意关系类型文本转换为合法的 Cypher 关系类型标识。
        仅保留 A-Z0-9_，其余替换为下划线；首字符若非法则加前缀 REL_。
        """
        try:
            import re as _re
            name = (raw or "").upper()
            name = _re.sub(r"[^A-Z0-9_]", "_", name)
            name = _re.sub(r"_+", "_", name).strip("_")
            if not name:
                return "RELATED"
            if not _re.match(r"^[A-Z_][A-Z0-9_]*$", name):
                name = f"REL_{name}"
                name = _re.sub(r"[^A-Z0-9_]", "_", name)
            return name
        except Exception:
            return "RELATED"

    def delete_edges_by_src(self, section_id: str) -> int:
        if not self.driver:
            return -1
        try:
            with self.driver.session(database=self.database) as session:
                cypher = """
                MATCH ()-[r]->() WHERE r.src = $section_id DELETE r RETURN count(r) as deleted_count
                """
                rec = session.run(cypher, {"section_id": section_id}).single()
                return int(rec["deleted_count"]) if rec else 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"删除边失败: {e}")
            return -1

    def delete_edges_by_scope(self, scope: str) -> int:
        """
        按scope删除关系，支持整本书和小节视图的独立清理。
        
        Args:
            scope: 范围标识，如 "section:xxx" 或 "book:xxx"
            
        Returns:
            删除的关系数量，失败返回-1
        """
        if not self.driver:
            return -1
        try:
            with self.driver.session(database=self.database) as session:
                cypher = """
                MATCH ()-[r]->() WHERE r.scope = $scope DELETE r RETURN count(r) as deleted_count
                """
                rec = session.run(cypher, {"scope": scope}).single()
                return int(rec["deleted_count"]) if rec else 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"按scope删除边失败: {e}")
            return -1

    def get_graph_stats(self) -> Dict[str, int]:
        if not self.driver:
            return {}
        stats: Dict[str, int] = {}
        try:
            with self.driver.session(database=self.database) as session:
                stats["total_nodes"] = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
                stats["total_edges"] = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
            return stats
        except Exception as e:  # noqa: BLE001
            logger.error(f"获取图统计失败: {e}")
            return {}

    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行任意 Cypher，并返回记录的字典列表（等价于 neo4j.Result.data()）。

        注意：仅用于受控读操作（如查询节点/边）。写操作请使用 merge_node/merge_edge 等专用方法。
        """
        if not self.driver:
            return []
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params or {})
                return result.data() or []
        except Exception as e:  # noqa: BLE001
            logger.error(f"执行 Cypher 失败: {e}")
            return []


def create_neo4j_client(config: Dict[str, Any]) -> Optional[Neo4jClient]:
    neo = (config or {}).get("neo4j", {})
    required = ["uri", "user", "password"]
    for k in required:
        if not neo.get(k):
            logger.error(f"Neo4j 配置缺少必需字段: {k}")
            return None
    client = Neo4jClient(
        uri=neo["uri"], user=neo["user"], password=neo["password"], database=neo.get("database", "neo4j")
    )
    return client if client.connect() else None


