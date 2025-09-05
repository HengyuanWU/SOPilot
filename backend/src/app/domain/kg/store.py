#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG Store - Neo4j写入，保证唯一约束
工程化分层设计中的第四层：将KG数据写入Neo4j数据库，确保数据一致性
"""

import logging
from typing import Protocol, Dict, Any, List, Optional
from abc import ABC, abstractmethod

from .schemas import KGNode, KGEdge, KGDict


logger = logging.getLogger(__name__)


class BaseKGStore(ABC):
    """KG存储基类"""
    
    @abstractmethod
    def store_kg(self, kg_data: KGDict, context: Dict[str, Any]) -> Dict[str, Any]:
        """存储KG数据"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, int]:
        """获取存储统计信息"""
        pass
    
    @abstractmethod
    def delete_by_scope(self, scope: str) -> int:
        """按scope删除数据"""
        pass


class Neo4jKGStore(BaseKGStore):
    """Neo4j KG存储实现"""
    
    def __init__(self, neo4j_client=None):
        self.neo4j_client = neo4j_client
        self.logger = logging.getLogger(__name__)
        
        if not self.neo4j_client:
            self._initialize_client()
        
        # 确保约束和索引存在
        self._ensure_constraints()
    
    def _initialize_client(self):
        """初始化Neo4j客户端"""
        try:
            from ...infrastructure.graph_store.neo4j_client import Neo4jClient
            from ...core.settings import get_settings
            
            settings = get_settings()
            self.neo4j_client = Neo4jClient(
                uri=settings.neo4j.uri,
                user=settings.neo4j.user,
                password=settings.neo4j.password,
                database=settings.neo4j.database
            )
            self.logger.info("Neo4j KG Store initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Neo4j client: {e}")
            self.neo4j_client = None
    
    def _ensure_constraints(self):
        """确保Neo4j约束和索引存在"""
        if not self.neo4j_client:
            return
        
        constraints_and_indexes = [
            # 节点唯一约束
            "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT chapter_id IF NOT EXISTS FOR (n:Chapter) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT subchapter_id IF NOT EXISTS FOR (n:Subchapter) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT method_id IF NOT EXISTS FOR (n:Method) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT example_id IF NOT EXISTS FOR (n:Example) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT dataset_id IF NOT EXISTS FOR (n:Dataset) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT equation_id IF NOT EXISTS FOR (n:Equation) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:Doc) REQUIRE n.id IS UNIQUE",
            
            # 索引
            "CREATE INDEX node_scope IF NOT EXISTS FOR (n) ON (n.scope)",
            "CREATE INDEX rel_scope IF NOT EXISTS FOR ()-[r]-() ON (r.scope)",
            "CREATE INDEX rel_rid IF NOT EXISTS FOR ()-[r]-() ON (r.rid)",
            "CREATE INDEX node_name IF NOT EXISTS FOR (n) ON (n.name)",
        ]
        
        for query in constraints_and_indexes:
            try:
                self.neo4j_client.execute_cypher(query)
            except Exception as e:
                # 约束可能已存在，这是正常的
                self.logger.debug(f"Constraint/Index query result: {e}")
    
    def store_kg(self, kg_data: KGDict, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        将KG数据存储到Neo4j
        
        Args:
            kg_data: 幂等处理后的KG数据
            context: 上下文信息
            
        Returns:
            Dict: 存储统计信息
        """
        if not self.neo4j_client:
            return {"success": False, "error": "Neo4j client not available"}
        
        try:
            stats = {
                "nodes_created": 0,
                "nodes_updated": 0,
                "edges_created": 0,
                "edges_updated": 0,
                "success": True
            }
            
            # 存储节点
            for node in kg_data.nodes:
                result = self._store_node(node)
                if result.get("created"):
                    stats["nodes_created"] += 1
                else:
                    stats["nodes_updated"] += 1
            
            # 存储边
            for edge in kg_data.edges:
                result = self._store_edge(edge)
                if result.get("created"):
                    stats["edges_created"] += 1
                else:
                    stats["edges_updated"] += 1
            
            self.logger.info(f"KG存储完成: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"KG存储失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _store_node(self, node: KGNode) -> Dict[str, Any]:
        """存储单个节点"""
        query = f"""
        MERGE (n:{node.type} {{id: $id}})
        SET n.name = $name,
            n.desc = $desc,
            n.aliases = $aliases,
            n.scope = $scope,
            n.updated_at = datetime($updated_at)
        ON CREATE SET n.created_at = datetime($created_at)
        RETURN n, 
               CASE WHEN n.created_at = datetime($created_at) THEN true ELSE false END as created
        """
        
        params = {
            "id": node.id,
            "name": node.name,
            "desc": node.desc or "",
            "aliases": node.aliases or [],
            "scope": node.scope or "",
            "created_at": node.created_at.isoformat() if node.created_at else "",
            "updated_at": node.updated_at.isoformat() if node.updated_at else ""
        }
        
        result = self.neo4j_client.execute_cypher(query, params)
        record = result[0] if result else None
        return {"created": record["created"] if record else False}
    
    def _store_edge(self, edge: KGEdge) -> Dict[str, Any]:
        """存储单个边"""
        # 动态关系类型需要特殊处理
        query = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        MERGE (source)-[r:{edge.type} {{rid: $rid}}]->(target)
        SET r.desc = $desc,
            r.confidence = $confidence,
            r.weight = $weight,
            r.scope = $scope,
            r.src_section = $src_section,
            r.updated_at = datetime($updated_at)
        ON CREATE SET r.created_at = datetime($created_at)
        RETURN r,
               CASE WHEN r.created_at = datetime($created_at) THEN true ELSE false END as created
        """
        
        params = {
            "source_id": edge.source,
            "target_id": edge.target,
            "rid": edge.rid,
            "desc": edge.desc or "",
            "confidence": edge.confidence,
            "weight": edge.weight,
            "scope": edge.scope or "",
            "src_section": edge.src_section or "",
            "created_at": edge.created_at.isoformat() if edge.created_at else "",
            "updated_at": edge.created_at.isoformat() if edge.created_at else ""  # 使用created_at作为updated_at的初始值
        }
        
        result = self.neo4j_client.execute_cypher(query, params)
        record = result[0] if result else None
        return {"created": record["created"] if record else False}
    
    def get_stats(self) -> Dict[str, int]:
        """获取Neo4j中的统计信息"""
        if not self.neo4j_client:
            return {"total_nodes": 0, "total_edges": 0}
        
        try:
            # 统计节点
            nodes_query = "MATCH (n) RETURN count(n) as total_nodes"
            nodes_result = self.neo4j_client.execute_cypher(nodes_query)
            total_nodes = nodes_result[0]["total_nodes"] if nodes_result else 0
            
            # 统计关系
            edges_query = "MATCH ()-[r]->() RETURN count(r) as total_edges"
            edges_result = self.neo4j_client.execute_cypher(edges_query)
            total_edges = edges_result[0]["total_edges"] if edges_result else 0
            
            return {"total_nodes": total_nodes, "total_edges": total_edges}
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"total_nodes": 0, "total_edges": 0}
    
    def delete_by_scope(self, scope: str) -> int:
        """按scope删除节点和关系"""
        if not self.neo4j_client or not scope:
            return 0

        try:
            # 删除关系
            edges_query = "MATCH ()-[r]-() WHERE r.scope = $scope DELETE r RETURN count(r) as deleted_edges"
            edges_result = self.neo4j_client.execute_cypher(edges_query, {"scope": scope})
            deleted_edges = edges_result[0]["deleted_edges"] if edges_result else 0
            
            # 删除孤立节点
            nodes_query = """
            MATCH (n) 
            WHERE n.scope = $scope AND NOT (n)-[]-() 
            DELETE n 
            RETURN count(n) as deleted_nodes
            """
            nodes_result = self.neo4j_client.execute_cypher(nodes_query, {"scope": scope})
            deleted_nodes = nodes_result[0]["deleted_nodes"] if nodes_result else 0
            
            self.logger.info(f"按scope删除: {deleted_edges} edges, {deleted_nodes} nodes")
            return deleted_edges + deleted_nodes
            
        except Exception as e:
            self.logger.error(f"按scope删除失败: {e}")
        return 0

    def delete_edges_by_src(self, section_id: str) -> int:
        """按src删除边（向后兼容方法）"""
        if not self.neo4j_client or not section_id:
            return 0
        
        try:
            # 删除指定src的关系
            query = "MATCH ()-[r]-() WHERE r.src = $section_id DELETE r RETURN count(r) as deleted_edges"
            result = self.neo4j_client.execute_cypher(query, {"section_id": section_id})
            deleted_edges = result[0]["deleted_edges"] if result else 0
            
            self.logger.info(f"按src删除: {deleted_edges} edges")
            return deleted_edges
            
        except Exception as e:
            self.logger.error(f"按src删除失败: {e}")
        return 0

    def merge_node(self, node: Dict[str, Any]) -> bool:
        """合并节点到Neo4j"""
        if not self.neo4j_client or not node:
            return False
        
        try:
            query = """
            MERGE (n {id: $id})
            SET n += $properties
            RETURN n.id as node_id
            """
            params = {
                "id": node.get("id"),
                "properties": node
            }
            result = self.neo4j_client.execute_cypher(query, params)
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"节点合并失败: {e}")
            return False

    def merge_edge(self, edge: Dict[str, Any]) -> bool:
        """合并边到Neo4j"""
        if not self.neo4j_client or not edge:
            return False
        
        try:
            # 使用rid作为关系的唯一标识
            query = """
            MATCH (source {id: $source_id})
            MATCH (target {id: $target_id})
            MERGE (source)-[r {rid: $rid}]->(target)
            SET r += $properties
            RETURN r.rid as edge_rid
            """
            params = {
                "source_id": edge.get("source_id"),
                "target_id": edge.get("target_id"),
                "rid": edge.get("rid"),
                "properties": edge
            }
            result = self.neo4j_client.execute_cypher(query, params)
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"边合并失败: {e}")
            return False


class MemoryKGStore(BaseKGStore):
    """内存KG存储实现（用于测试和开发）"""
    
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
    
    def store_kg(self, kg_data: KGDict, context: Dict[str, Any]) -> Dict[str, Any]:
        """存储KG数据到内存"""
        try:
            stats = {
                "nodes_created": 0,
                "nodes_updated": 0,
                "edges_created": 0,
                "edges_updated": 0,
                "success": True
            }
            
            # 存储节点
            for node in kg_data.nodes:
                if node.id in self.nodes:
                    stats["nodes_updated"] += 1
                else:
                    stats["nodes_created"] += 1
                
                self.nodes[node.id] = {
                    "id": node.id,
                    "name": node.name,
                    "type": node.type,
                    "desc": node.desc,
                    "aliases": node.aliases,
                    "scope": node.scope,
                    "created_at": node.created_at,
                    "updated_at": node.updated_at
                }
            
            # 存储边
            for edge in kg_data.edges:
                if edge.rid in self.edges:
                    stats["edges_updated"] += 1
                else:
                    stats["edges_created"] += 1
                
                self.edges[edge.rid] = {
                    "rid": edge.rid,
                    "type": edge.type,
                    "source": edge.source,
                    "target": edge.target,
                    "desc": edge.desc,
                    "confidence": edge.confidence,
                    "weight": edge.weight,
                    "scope": edge.scope,
                    "src_section": edge.src_section,
                    "created_at": edge.created_at
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"内存KG存储失败: {e}")
            return {"success": False, "error": str(e)}

    def get_stats(self) -> Dict[str, int]:
        """获取内存存储统计信息"""
        return {"total_nodes": len(self.nodes), "total_edges": len(self.edges)}
    
    def delete_by_scope(self, scope: str) -> int:
        """按scope删除数据"""
        if not scope:
            return 0
        
        # 删除边
        edges_to_delete = [rid for rid, edge in self.edges.items() if edge.get("scope") == scope]
        for rid in edges_to_delete:
            del self.edges[rid]
        
        # 删除节点
        nodes_to_delete = [nid for nid, node in self.nodes.items() if node.get("scope") == scope]
        for nid in nodes_to_delete:
            del self.nodes[nid]
        
        return len(edges_to_delete) + len(nodes_to_delete)


def create_kg_store(store_type: str = "neo4j", **kwargs) -> BaseKGStore:
    """创建KG存储实例"""
    if store_type.lower() == "neo4j":
        return Neo4jKGStore(**kwargs)
    elif store_type.lower() == "memory":
        return MemoryKGStore(**kwargs)
    else:
        raise ValueError(f"Unknown store type: {store_type}")


# 保持向后兼容性
class KGStore(Protocol):
    def merge_node(self, node: Dict[str, Any]) -> bool: ...
    def merge_edge(self, edge: Dict[str, Any]) -> bool: ...
    def delete_edges_by_src(self, section_id: str) -> int: ...
    def get_stats(self) -> Dict[str, int]: ...
    def delete_edges_by_scope(self, scope: str) -> int: ...

