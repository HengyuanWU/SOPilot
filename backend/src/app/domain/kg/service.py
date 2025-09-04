#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG Service - 查询API服务层
工程化分层设计中的第六层：提供统一的KG查询接口，供前端和其他服务调用
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod

from .schemas import KGNode, KGEdge, KGDict


logger = logging.getLogger(__name__)


class BaseKGService(ABC):
    """KG服务基类"""
    
    @abstractmethod
    def get_node_detail(self, node_id: str, scope: str = None) -> Optional[Dict[str, Any]]:
        """获取节点详情"""
        pass
    
    @abstractmethod
    def get_edge_detail(self, edge_rid: str, scope: str = None) -> Optional[Dict[str, Any]]:
        """获取关系详情"""
        pass
    
    @abstractmethod
    def get_subgraph(self, center_node: str, scope: str = None, max_depth: int = 2, limit: int = 50) -> Dict[str, Any]:
        """获取子图"""
        pass
    
    @abstractmethod
    def search_nodes(self, query: str, scope: str = None, node_types: List[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索节点"""
        pass


class Neo4jKGService(BaseKGService):
    """基于Neo4j的KG服务实现"""
    
    def __init__(self, neo4j_client=None):
        self.neo4j_client = neo4j_client
        self.logger = logging.getLogger(__name__)
        
        if not self.neo4j_client:
            self._initialize_client()
    
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
            self.logger.info("Neo4j KG Service initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Neo4j client: {e}")
            self.neo4j_client = None
    
    def get_node_detail(self, node_id: str, scope: str = None) -> Optional[Dict[str, Any]]:
        """
        获取节点详情
        
        Args:
            node_id: 节点ID
            scope: 范围限制（Book Scope）
            
        Returns:
            Dict: 节点详情，包含基本信息 + 来源Section + 证据Chunk IDs
        """
        if not self.neo4j_client or not node_id:
            return None
        
        try:
            # 构建查询
            where_clause = "n.id = $node_id"
            params = {"node_id": node_id}
            
            if scope:
                where_clause += " AND n.scope = $scope"
                params["scope"] = scope
            
            query = f"""
            MATCH (n)
            WHERE {where_clause}
            OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(n)
            RETURN n,
                   labels(n) as node_labels,
                   collect(DISTINCT c.id)[..10] as chunk_ids,
                   count(DISTINCT c) as evidence_count
            LIMIT 1
            """
            
            result = self.neo4j_client.execute_query(query, params)
            
            if not result.records:
                return None
            
            record = result.records[0]
            node = record["n"]
            
            return {
                "id": node.get("id"),
                "name": node.get("name"),
                "type": record["node_labels"][0] if record["node_labels"] else "Unknown",
                "desc": node.get("desc", ""),
                "aliases": node.get("aliases", []),
                "scope": node.get("scope"),
                "created_at": node.get("created_at"),
                "updated_at": node.get("updated_at"),
                "chunk_ids": record["chunk_ids"],
                "evidence_count": record["evidence_count"]
            }
            
        except Exception as e:
            self.logger.error(f"获取节点详情失败: {e}")
            return None
    
    def get_edge_detail(self, edge_rid: str, scope: str = None) -> Optional[Dict[str, Any]]:
        """
        获取关系详情
        
        Args:
            edge_rid: 关系ID
            scope: 范围限制
            
        Returns:
            Dict: 关系详情，包含confidence、weight、解释路径
        """
        if not self.neo4j_client or not edge_rid:
            return None
        
        try:
            where_clause = "r.rid = $edge_rid"
            params = {"edge_rid": edge_rid}
            
            if scope:
                where_clause += " AND r.scope = $scope"
                params["scope"] = scope
            
            query = f"""
            MATCH (source)-[r]->(target)
            WHERE {where_clause}
            RETURN r, source, target, type(r) as rel_type
            LIMIT 1
            """
            
            result = self.neo4j_client.execute_query(query, params)
            
            if not result.records:
                return None
            
            record = result.records[0]
            rel = record["r"]
            source = record["source"]
            target = record["target"]
            
            return {
                "rid": rel.get("rid"),
                "type": record["rel_type"],
                "desc": rel.get("desc", ""),
                "confidence": rel.get("confidence", 0.0),
                "weight": rel.get("weight", 1.0),
                "scope": rel.get("scope"),
                "src_section": rel.get("src_section"),
                "created_at": rel.get("created_at"),
                "source": {
                    "id": source.get("id"),
                    "name": source.get("name"),
                    "type": list(source.labels)[0] if source.labels else "Unknown"
                },
                "target": {
                    "id": target.get("id"),
                    "name": target.get("name"),
                    "type": list(target.labels)[0] if target.labels else "Unknown"
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取关系详情失败: {e}")
            return None
    
    def get_subgraph(self, center_node: str, scope: str = None, max_depth: int = 2, limit: int = 50) -> Dict[str, Any]:
        """
        获取子图（邻居展开/解释路径/证据回链）
        
        Args:
            center_node: 中心节点ID
            scope: 范围限制
            max_depth: 最大深度
            limit: 结果限制
            
        Returns:
            Dict: 子图数据，包含nodes和edges
        """
        if not self.neo4j_client or not center_node:
            return {"nodes": [], "edges": []}
        
        try:
            where_clause = "center.id = $center_node"
            params = {"center_node": center_node, "max_depth": max_depth, "limit": limit}
            
            if scope:
                where_clause += " AND center.scope = $scope"
                params["scope"] = scope
            
            # 实体邻接子图查询（带证据）
            query = f"""
            MATCH (center)
            WHERE {where_clause}
            OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(center)
            WITH center, collect(DISTINCT c.id)[..10] AS center_chunk_ids
            MATCH path = (center)-[r*1..{max_depth}]-(neighbor)
            WHERE ALL(rel in relationships(path) WHERE 
                      (NOT $scope IS NULL) = (rel.scope = $scope OR $scope IS NULL))
            WITH center, center_chunk_ids, path, neighbor, relationships(path) as rels
            LIMIT $limit
            RETURN center,
                   center_chunk_ids,
                   collect(DISTINCT neighbor) as neighbors,
                   collect(DISTINCT path) as paths,
                   collect(DISTINCT rels) as all_rels
            """
            
            result = self.neo4j_client.execute_query(query, params)
            
            if not result.records:
                return {"nodes": [], "edges": []}
            
            record = result.records[0]
            
            # 处理节点
            nodes = []
            center = record["center"]
            nodes.append({
                "id": center.get("id"),
                "name": center.get("name"),
                "type": list(center.labels)[0] if center.labels else "Unknown",
                "desc": center.get("desc", ""),
                "chunk_ids": record["center_chunk_ids"],
                "is_center": True
            })
            
            # 添加邻居节点
            for neighbor in record["neighbors"]:
                if neighbor.get("id") != center.get("id"):
                    nodes.append({
                        "id": neighbor.get("id"),
                        "name": neighbor.get("name"),
                        "type": list(neighbor.labels)[0] if neighbor.labels else "Unknown",
                        "desc": neighbor.get("desc", ""),
                        "is_center": False
                    })
            
            # 处理关系
            edges = []
            for rel_group in record["all_rels"]:
                for rel in rel_group:
                    edges.append({
                        "rid": rel.get("rid"),
                        "type": rel.type,
                        "source": rel.start_node.get("id"),
                        "target": rel.end_node.get("id"),
                        "desc": rel.get("desc", ""),
                        "confidence": rel.get("confidence", 0.0),
                        "weight": rel.get("weight", 1.0)
                    })
            
            return {
                "center_node": center_node,
                "nodes": nodes,
                "edges": edges,
                "total_nodes": len(nodes),
                "total_edges": len(edges)
            }
            
        except Exception as e:
            self.logger.error(f"获取子图失败: {e}")
            return {"nodes": [], "edges": []}
    
    def search_nodes(self, query: str, scope: str = None, node_types: List[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索节点
        
        Args:
            query: 搜索查询
            scope: 范围限制
            node_types: 节点类型限制
            limit: 结果限制
            
        Returns:
            List[Dict]: 搜索结果
        """
        if not self.neo4j_client or not query:
            return []
        
        try:
            # 构建WHERE子句
            where_conditions = []
            params = {"query": query.lower(), "limit": limit}
            
            # 名称匹配条件
            where_conditions.append("(toLower(n.name) CONTAINS $query OR ANY(alias in n.aliases WHERE toLower(alias) CONTAINS $query))")
            
            if scope:
                where_conditions.append("n.scope = $scope")
                params["scope"] = scope
            
            if node_types:
                # 构建标签条件
                label_conditions = " OR ".join([f"n:{node_type}" for node_type in node_types])
                where_conditions.append(f"({label_conditions})")
            
            where_clause = " AND ".join(where_conditions)
            
            query_cypher = f"""
            MATCH (n)
            WHERE {where_clause}
            RETURN n, labels(n) as node_labels
            ORDER BY 
                CASE WHEN toLower(n.name) = $query THEN 1 ELSE 2 END,
                CASE WHEN toLower(n.name) STARTS WITH $query THEN 1 ELSE 2 END,
                n.name
            LIMIT $limit
            """
            
            result = self.neo4j_client.execute_query(query_cypher, params)
            
            nodes = []
            for record in result.records:
                node = record["n"]
                nodes.append({
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "type": record["node_labels"][0] if record["node_labels"] else "Unknown",
                    "desc": node.get("desc", ""),
                    "aliases": node.get("aliases", []),
                    "scope": node.get("scope")
                })
            
            return nodes
            
        except Exception as e:
            self.logger.error(f"搜索节点失败: {e}")
            return []
    
    def get_chunk_related_entities(self, chunk_id: str, scope: str = None, limit: int = 30) -> Dict[str, Any]:
        """
        由Chunk反查相关实体（KG×RAG联动查询）
        
        Args:
            chunk_id: Chunk ID
            scope: 范围限制
            limit: 结果限制
            
        Returns:
            Dict: 相关实体和关系路径
        """
        if not self.neo4j_client or not chunk_id:
            return {"entities": [], "paths": []}
        
        try:
            where_clause = "c.id = $chunk_id"
            params = {"chunk_id": chunk_id, "limit": limit}
            
            if scope:
                where_clause += " AND e.scope = $scope"
                params["scope"] = scope
            
            query = f"""
            MATCH (c:Chunk)-[:MENTIONS]->(e)
            WHERE {where_clause}
            OPTIONAL MATCH path = (e)-[r*1..2]-(related)
            WHERE ALL(rel in relationships(path) WHERE 
                      (NOT $scope IS NULL) = (rel.scope = $scope OR $scope IS NULL))
            RETURN e, 
                   labels(e) as entity_labels,
                   collect(DISTINCT path) as paths,
                   collect(DISTINCT related) as related_entities
            LIMIT $limit
            """
            
            result = self.neo4j_client.execute_query(query, params)
            
            entities = []
            all_paths = []
            
            for record in result.records:
                entity = record["e"]
                entities.append({
                    "id": entity.get("id"),
                    "name": entity.get("name"),
                    "type": record["entity_labels"][0] if record["entity_labels"] else "Unknown",
                    "desc": entity.get("desc", "")
                })
                
                # 处理路径
                for path in record["paths"]:
                    if path:  # 确保路径不为空
                        path_info = {
                            "length": len(path.relationships),
                            "nodes": [{"id": n.get("id"), "name": n.get("name")} for n in path.nodes],
                            "relationships": [{"type": r.type, "desc": r.get("desc", "")} for r in path.relationships]
                        }
                        all_paths.append(path_info)
            
            return {
                "chunk_id": chunk_id,
                "entities": entities,
                "paths": all_paths[:20],  # 限制路径数量
                "total_entities": len(entities)
            }
            
        except Exception as e:
            self.logger.error(f"Chunk反查实体失败: {e}")
            return {"entities": [], "paths": []}
    
    def get_book_stats(self, book_id: str) -> Dict[str, Any]:
        """获取整书统计信息"""
        if not self.neo4j_client or not book_id:
            return {}
        
        try:
            query = """
            MATCH (n) WHERE n.scope = $book_id
            OPTIONAL MATCH ()-[r]->() WHERE r.scope = $book_id
            RETURN 
                count(DISTINCT n) as total_nodes,
                count(DISTINCT r) as total_edges,
                collect(DISTINCT labels(n)) as node_types,
                collect(DISTINCT type(r)) as edge_types
            """
            
            result = self.neo4j_client.execute_query(query, {"book_id": book_id})
            
            if result.records:
                record = result.records[0]
                return {
                    "book_id": book_id,
                    "total_nodes": record["total_nodes"],
                    "total_edges": record["total_edges"],
                    "node_types": [t for types in record["node_types"] for t in types if types],
                    "edge_types": [t for t in record["edge_types"] if t]
                }
            
            return {}
            
        except Exception as e:
            self.logger.error(f"获取整书统计失败: {e}")
            return {}


class MemoryKGService(BaseKGService):
    """基于内存的KG服务实现（用于测试）"""
    
    def __init__(self, memory_store=None):
        self.memory_store = memory_store
        self.logger = logging.getLogger(__name__)
    
    def get_node_detail(self, node_id: str, scope: str = None) -> Optional[Dict[str, Any]]:
        """获取节点详情（内存版本）"""
        if not self.memory_store or not node_id:
            return None
        
        node = self.memory_store.nodes.get(node_id)
        if not node:
            return None
        
        if scope and node.get("scope") != scope:
            return None
        
        return node
    
    def get_edge_detail(self, edge_rid: str, scope: str = None) -> Optional[Dict[str, Any]]:
        """获取关系详情（内存版本）"""
        if not self.memory_store or not edge_rid:
            return None
        
        edge = self.memory_store.edges.get(edge_rid)
        if not edge:
            return None
        
        if scope and edge.get("scope") != scope:
            return None
        
        return edge
    
    def get_subgraph(self, center_node: str, scope: str = None, max_depth: int = 2, limit: int = 50) -> Dict[str, Any]:
        """获取子图（内存版本）"""
        # TODO: 实现内存版本的子图查询
        return {"nodes": [], "edges": []}
    
    def search_nodes(self, query: str, scope: str = None, node_types: List[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索节点（内存版本）"""
        if not self.memory_store or not query:
            return []
        
        results = []
        query_lower = query.lower()
        
        for node in self.memory_store.nodes.values():
            if scope and node.get("scope") != scope:
                continue
            
            if node_types and node.get("type") not in node_types:
                continue
            
            name = node.get("name", "").lower()
            if query_lower in name:
                results.append(node)
            
            if len(results) >= limit:
                break
        
        return results


def create_kg_service(service_type: str = "neo4j", **kwargs) -> BaseKGService:
    """创建KG服务实例"""
    if service_type.lower() == "neo4j":
        return Neo4jKGService(**kwargs)
    elif service_type.lower() == "memory":
        return MemoryKGService(**kwargs)
    else:
        raise ValueError(f"Unknown service type: {service_type}")