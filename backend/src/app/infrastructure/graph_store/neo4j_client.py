#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j 客户端（基础设施层）- 适配器模式
内部使用 neomodel 统一网关，保持外部 API 兼容性。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neomodel import config, db
from .neomodel_store import Neo4jStore

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 客户端适配器：使用 neomodel 作为底层实现。
    
    保持原有 API 兼容性，内部委托给 Neo4jStore 网关。
    """
    
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        """初始化客户端（不会立即连接）。
        
        Args:
            uri: Neo4j 连接 URI (bolt://...)
            user: 用户名
            password: 密码
            database: 数据库名（neomodel 需要在 URI 中指定）
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._connected = False

    def connect(self) -> bool:
        """配置 neomodel 连接并测试连通性。
        
        Returns:
            连接成功返回 True，失败返回 False
        """
        try:
            # 构建 neomodel 连接 URL（格式：bolt://user:password@host:port/database）
            # 从 URI 提取 host:port 部分
            host_part = self.uri.replace("bolt://", "").replace("neo4j://", "")
            bolt_url = f"bolt://{self.user}:{self.password}@{host_part}"
            if self.database and self.database != "neo4j":
                bolt_url = f"{bolt_url}/{self.database}"
            
            # 配置 neomodel
            config.DATABASE_URL = bolt_url
            config.MAX_POOL_SIZE = 50
            
            # 测试连接
            result = Neo4jStore.run_cypher("RETURN 1 as test")
            if result and result[0].get("test") == 1:
                self._connected = True
                logger.info(f"Neo4j 连接成功: {self.uri}")
                return True
            return False
        except Exception as e:  # noqa: BLE001
            logger.error(f"Neo4j 连接失败: {e}")
            self._connected = False
            return False

    def close(self) -> None:
        """关闭连接（neomodel 自动管理连接池，此方法保持 API 兼容）。"""
        if self._connected:
            try:
                # neomodel 的连接池自动管理，不需要显式关闭
                # 只标记为未连接状态
                self._connected = False
                logger.info("Neo4j 连接标记为已关闭")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"关闭连接时出错: {e}")

    def merge_node(self, node: Dict[str, Any]) -> bool:
        """合并节点到图数据库。
        
        Args:
            node: 节点字典，必须包含 'id' 和 'type' 字段
            
        Returns:
            成功返回 True，失败返回 False
        """
        if not self._connected:
            return False
        try:
            node_type = str(node.get("type") or "Node").strip()
            labels = self._validate_label(node_type)
            
            cypher = f"""
            MERGE (n:{labels} {{id: $id}})
            SET n += $properties
            SET n.updated_at = datetime()
            SET n.created_at = COALESCE(n.created_at, datetime())
            RETURN n.id as node_id
            """
            
            props = dict(node)
            # 移除created_at，让Neo4j自己生成
            props.pop("created_at", None)
            
            result = Neo4jStore.run_cypher(cypher, {"id": node["id"], "properties": props})
            return len(result) > 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"合并节点失败: {e}")
            return False

    def merge_edge(self, edge: Dict[str, Any]) -> bool:
        """合并边到图数据库。
        
        Args:
            edge: 边字典，必须包含 'source_id', 'target_id', 'type' 字段
            
        Returns:
            成功返回 True，失败返回 False
        """
        if not self._connected:
            return False
        try:
            edge_type_raw = str(edge.get("type", "")).strip()
            edge_type = self._validate_rel_type(edge_type_raw)
            
            # 使用rid做唯一匹配（如果提供了rid）
            rid = edge.get("rid")
            # 准备属性字典（确保source_id/target_id在其中）
            props = dict(edge)
            if edge_type_raw:
                props["type_label"] = edge_type_raw
            if "id" not in props:
                props["id"] = f"{edge_type}:{edge.get('source_id')}->{edge.get('target_id')}"
            # 移除created_at，让Neo4j自己生成
            props.pop("created_at", None)
            
            # 确保source_id和target_id在properties中
            props["source_id"] = edge["source_id"]
            props["target_id"] = edge["target_id"]
            
            if rid:
                cypher = f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                MERGE (source)-[r:{edge_type}]->(target)
                SET r.rid = $rid,
                    r.source_id = $source_id,
                    r.target_id = $target_id,
                    r += $properties,
                    r.updated_at = datetime(),
                    r.created_at = COALESCE(r.created_at, datetime())
                RETURN r.id as edge_id
                """
                params = {
                    "source_id": edge["source_id"],
                    "target_id": edge["target_id"],
                    "rid": rid,
                    "properties": props,
                }
            else:
                # 兼容旧逻辑：不使用rid
                cypher = f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                MERGE (source)-[r:{edge_type}]->(target)
                SET r.source_id = $source_id,
                    r.target_id = $target_id,
                    r += $properties,
                    r.updated_at = datetime(),
                    r.created_at = COALESCE(r.created_at, datetime())
                RETURN r.id as edge_id
                """
                params = {
                    "source_id": edge["source_id"],
                    "target_id": edge["target_id"],
                    "properties": props,
                }
            
            result = Neo4jStore.run_cypher(cypher, params)
            return len(result) > 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"合并边失败: {e}")
            return False

    def _validate_label(self, raw: str) -> str:
        """严格白名单校验节点标签，避免注入。"""
        allowed = {
            "Node",
            "Concept",
            "Chapter",
            "Subchapter",
            "Method",
            "Example",
            "Dataset",
            "Equation",
            "Doc",
            "Chunk",
            "Entity",
        }
        name = (raw or "Node").strip()
        if name not in allowed:
            logger.warning(f"非法标签'{name}'，回退為 'Node'")
            return "Node"
        return name

    def _validate_rel_type(self, raw: str) -> str:
        """严格白名单/正则校验关系类型，避免注入。"""
        allowed = {
            "HAS_CHUNK",
            "MENTIONS",
            "RELATED",
            "RELATED_TO",
            "PART_OF",
            "INSTANCE_OF",
        }
        name = (raw or "RELATED").strip().upper()
        if name in allowed:
            return name
        # 允許符合正則的企業自定義，但限制字符集
        import re as _re  # noqa: PLC0415
        if _re.match(r"^[A-Z_][A-Z0-9_]*$", name):
            return name
        logger.warning(f"非法关系类型'{name}'，回退為 'RELATED'")
        return "RELATED"

    def delete_edges_by_src(self, section_id: str) -> int:
        """根据 src 字段删除边。
        
        Args:
            section_id: 小节 ID
            
        Returns:
            删除的边数量，失败返回 -1
        """
        if not self._connected:
            return -1
        try:
            cypher = """
            MATCH ()-[r]->() WHERE r.src = $section_id DELETE r RETURN count(r) as deleted_count
            """
            result = Neo4jStore.run_cypher(cypher, {"section_id": section_id})
            return int(result[0]["deleted_count"]) if result else 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"删除边失败: {e}")
            return -1

    def delete_edges_by_scope(self, scope: str) -> int:
        """按 scope 删除关系，支持整本书和小节视图的独立清理。
        
        Args:
            scope: 范围标识，如 "section:xxx" 或 "book:xxx"
            
        Returns:
            删除的关系数量，失败返回 -1
        """
        if not self._connected:
            return -1
        try:
            cypher = """
            MATCH ()-[r]->() WHERE r.scope = $scope DELETE r RETURN count(r) as deleted_count
            """
            result = Neo4jStore.run_cypher(cypher, {"scope": scope})
            return int(result[0]["deleted_count"]) if result else 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"按scope删除边失败: {e}")
            return -1

    def get_graph_stats(self) -> Dict[str, int]:
        """获取图数据库统计信息。
        
        Returns:
            包含 total_nodes 和 total_edges 的字典
        """
        if not self._connected:
            return {}
        stats: Dict[str, int] = {}
        try:
            result_nodes = Neo4jStore.run_cypher("MATCH (n) RETURN count(n) as c")
            result_edges = Neo4jStore.run_cypher("MATCH ()-[r]->() RETURN count(r) as c")
            
            stats["total_nodes"] = int(result_nodes[0]["c"]) if result_nodes else 0
            stats["total_edges"] = int(result_edges[0]["c"]) if result_edges else 0
            return stats
        except Exception as e:  # noqa: BLE001
            logger.error(f"获取图统计失败: {e}")
            return {}

    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行任意 Cypher 查询，返回记录的字典列表。

        注意：仅用于受控读操作（如查询节点/边）。写操作请使用 merge_node/merge_edge 等专用方法。
        
        Args:
            query: Cypher 查询语句
            params: 查询参数字典
            
        Returns:
            查询结果的字典列表
        """
        if not self._connected:
            return []
        try:
            return Neo4jStore.run_cypher(query, params or {})
        except Exception as e:  # noqa: BLE001
            logger.error(f"执行 Cypher 失败: {e}")
            return []
    
    def execute_transaction(self, queries: List[tuple]) -> bool:
        """在单个事务中执行多个查询。
        
        Args:
            queries: [(query, params), ...] 查询和参数的元组列表
            
        Returns:
            成功返回 True，失败返回 False
        """
        if not self._connected:
            return False
        try:
            Neo4jStore.run_tx(queries)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"执行事务失败: {e}")
            return False


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


