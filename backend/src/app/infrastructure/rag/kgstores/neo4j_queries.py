#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j KG Queries - Neo4j知识图谱查询

提供知识图谱的检索查询功能，包括实体查找、路径查询、子图获取等
与现有的Neo4j基础设施集成
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KGSearchResult:
    """KG搜索结果"""
    type: str  # "entity", "path", "subgraph"
    score: float
    data: Dict[str, Any]
    path: Optional[List[Dict[str, Any]]] = None
    explanation: Optional[str] = None


class Neo4jKGQueries:
    """Neo4j知识图谱查询器"""
    
    def __init__(self, neo4j_client=None):
        """
        初始化查询器
        
        Args:
            neo4j_client: Neo4j客户端（可选，如果不提供会从现有基础设施获取）
        """
        self.logger = logging.getLogger(__name__)
        self._client = neo4j_client
        
        if self._client is None:
            self._client = self._get_neo4j_client()
    
    def _get_neo4j_client(self):
        """获取Neo4j客户端（从现有基础设施）"""
        try:
            from app.infrastructure.graph_store.neo4j_client import Neo4jClient
            from app.core.settings import get_settings
            
            settings = get_settings()
            return Neo4jClient(
                uri=settings.neo4j.uri,
                user=settings.neo4j.user,
                password=settings.neo4j.password,
                database=settings.neo4j.database
            )
        except Exception as e:
            self.logger.error(f"获取Neo4j客户端失败: {e}")
            raise
    
    def search_entities(self, query: str, entity_types: List[str] = None, limit: int = 10, scope: str = None) -> List[KGSearchResult]:
        """
        搜索实体
        
        Args:
            query: 搜索查询
            entity_types: 实体类型过滤 (如 ["Concept", "Method"])
            limit: 结果数量限制
            scope: 范围过滤 (如 book_id)
            
        Returns:
            List[KGSearchResult]: 搜索结果
        """
        try:
            # 构建Cypher查询
            cypher_parts = []
            params = {"query": query.lower(), "limit": limit}
            
            # 基础匹配
            if entity_types:
                # 指定类型的实体
                types_str = "|".join(entity_types)
                cypher_parts.append(f"MATCH (n:{types_str})")
                
            else:
                # 所有实体
                cypher_parts.append("MATCH (n)")
            
            # 搜索条件
            conditions = []
            conditions.append("(toLower(n.name) CONTAINS $query OR toLower(n.desc) CONTAINS $query)")
            
            # 如果有别名字段，也搜索别名
            conditions.append("(ANY(alias IN n.aliases WHERE toLower(alias) CONTAINS $query))")
            
            # 范围过滤
            if scope:
                conditions.append("n.scope = $scope")
                params["scope"] = scope
            
            cypher_parts.append("WHERE " + " OR ".join(conditions))
            
            # 返回结果并计算相关性分数
            cypher_parts.append("""
                RETURN n,
                       CASE 
                           WHEN toLower(n.name) = $query THEN 1.0
                           WHEN toLower(n.name) CONTAINS $query THEN 0.8
                           WHEN ANY(alias IN n.aliases WHERE toLower(alias) = $query) THEN 0.9
                           WHEN ANY(alias IN n.aliases WHERE toLower(alias) CONTAINS $query) THEN 0.7
                           WHEN toLower(n.desc) CONTAINS $query THEN 0.6
                           ELSE 0.5
                       END as score
                ORDER BY score DESC
                LIMIT $limit
            """)
            
            cypher = " ".join(cypher_parts)
            
            # 执行查询
            results = []
            records = self._client.execute_cypher(cypher, params)
            
            for record in records:
                entity = record["n"]
                score = record["score"]
                
                results.append(KGSearchResult(
                    type="entity",
                    score=float(score),
                    data={
                        "id": entity.get("id"),
                        "name": entity.get("name"),
                        "type": list(entity.labels)[0] if entity.labels else "Unknown",
                        "desc": entity.get("desc"),
                        "properties": dict(entity),
                    }
                ))
            
            self.logger.debug(f"实体搜索完成: query='{query}', 结果数={len(results)}")
            return results
            
        except Exception as e:
            self.logger.error(f"实体搜索失败: {e}")
            return []
    
    def get_entity_subgraph(self, entity_id: str, hop: int = 2, rel_types: List[str] = None, limit: int = 50) -> List[KGSearchResult]:
        """
        获取实体的邻接子图
        
        Args:
            entity_id: 实体ID
            hop: 跳数限制
            rel_types: 关系类型过滤
            limit: 结果数量限制
            
        Returns:
            List[KGSearchResult]: 子图结果
        """
        try:
            # 构建关系类型过滤
            rel_filter = ""
            if rel_types:
                rel_filter = f":{':'.join(rel_types)}"
            
            cypher = f"""
                MATCH (start {{id: $entity_id}})
                MATCH path = (start)-[r{rel_filter}*1..{hop}]-(end)
                WHERE start <> end
                WITH path, relationships(path) as rels, nodes(path) as nodes
                RETURN path, rels, nodes,
                       length(path) as path_length,
                       reduce(score = 1.0, rel in rels | 
                           score * COALESCE(rel.confidence, 0.8) * COALESCE(rel.weight, 1.0)
                       ) as path_score
                ORDER BY path_score DESC, path_length ASC
                LIMIT $limit
            """
            
            params = {"entity_id": entity_id, "limit": limit}
            records = self._client.execute_cypher(cypher, params)
            
            results = []
            for record in records:
                path = record["path"]
                path_score = record["path_score"]
                path_length = record["path_length"]
                
                # 构建路径表示
                path_nodes = []
                path_rels = []
                
                for node in record["nodes"]:
                    path_nodes.append({
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "type": list(node.labels)[0] if node.labels else "Unknown",
                    })
                
                for rel in record["rels"]:
                    path_rels.append({
                        "type": rel.type,
                        "confidence": rel.get("confidence", 0.8),
                        "weight": rel.get("weight", 1.0),
                    })
                
                # 生成路径说明
                explanation = self._generate_path_explanation(path_nodes, path_rels)
                
                results.append(KGSearchResult(
                    type="subgraph",
                    score=float(path_score / path_length),  # 归一化分数
                    data={
                        "path_length": path_length,
                        "nodes": path_nodes,
                        "relationships": path_rels,
                    },
                    explanation=explanation
                ))
            
            self.logger.debug(f"子图查询完成: entity_id='{entity_id}', hop={hop}, 结果数={len(results)}")
            return results
            
        except Exception as e:
            self.logger.error(f"子图查询失败: {e}")
            return []
    
    def find_shortest_path(self, start_entity: str, end_entity: str, max_hop: int = 3, rel_types: List[str] = None) -> List[KGSearchResult]:
        """
        查找两个实体之间的最短路径
        
        Args:
            start_entity: 起始实体名称或ID
            end_entity: 目标实体名称或ID
            max_hop: 最大跳数
            rel_types: 关系类型过滤
            
        Returns:
            List[KGSearchResult]: 路径结果
        """
        try:
            # 构建关系类型过滤
            rel_filter = ""
            if rel_types:
                rel_filter = f":{':'.join(rel_types)}"
            
            cypher = f"""
                MATCH (start), (end)
                WHERE (start.id = $start_entity OR start.name = $start_entity)
                  AND (end.id = $end_entity OR end.name = $end_entity)
                MATCH path = shortestPath((start)-[r{rel_filter}*1..{max_hop}]-(end))
                RETURN path, length(path) as path_length,
                       nodes(path) as nodes, relationships(path) as rels
            """
            
            params = {
                "start_entity": start_entity,
                "end_entity": end_entity
            }
            
            records = self._client.execute_cypher(cypher, params)
            
            results = []
            for record in records:
                path_length = record["path_length"]
                
                # 构建路径表示
                path_nodes = []
                path_rels = []
                
                for node in record["nodes"]:
                    path_nodes.append({
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "type": list(node.labels)[0] if node.labels else "Unknown",
                    })
                
                for rel in record["rels"]:
                    path_rels.append({
                        "type": rel.type,
                        "confidence": rel.get("confidence", 0.8),
                        "weight": rel.get("weight", 1.0),
                    })
                
                # 计算路径分数
                path_score = 1.0 / (path_length + 1)  # 越短路径分数越高
                
                # 生成路径说明
                explanation = self._generate_path_explanation(path_nodes, path_rels)
                
                results.append(KGSearchResult(
                    type="path",
                    score=path_score,
                    data={
                        "start_entity": start_entity,
                        "end_entity": end_entity,
                        "path_length": path_length,
                        "nodes": path_nodes,
                        "relationships": path_rels,
                    },
                    explanation=explanation
                ))
            
            self.logger.debug(f"路径查询完成: '{start_entity}' -> '{end_entity}', 结果数={len(results)}")
            return results
            
        except Exception as e:
            self.logger.error(f"路径查询失败: {e}")
            return []
    
    def get_entities_by_chunks(self, chunk_ids: List[str]) -> List[KGSearchResult]:
        """
        根据文档块ID获取相关实体（通过MENTIONS关系）
        
        Args:
            chunk_ids: 文档块ID列表
            
        Returns:
            List[KGSearchResult]: 相关实体结果
        """
        try:
            cypher = """
                MATCH (chunk:Chunk)-[:MENTIONS]->(entity)
                WHERE chunk.id IN $chunk_ids
                WITH entity, count(chunk) as mention_count
                RETURN entity, mention_count,
                       (mention_count * 1.0 / size($chunk_ids)) as relevance_score
                ORDER BY relevance_score DESC, mention_count DESC
            """
            
            params = {"chunk_ids": chunk_ids}
            records = self._client.execute_cypher(cypher, params)
            
            results = []
            for record in records:
                entity = record["entity"]
                mention_count = record["mention_count"]
                relevance_score = record["relevance_score"]
                
                results.append(KGSearchResult(
                    type="entity",
                    score=float(relevance_score),
                    data={
                        "id": entity.get("id"),
                        "name": entity.get("name"),
                        "type": list(entity.labels)[0] if entity.labels else "Unknown",
                        "desc": entity.get("desc"),
                        "mention_count": mention_count,
                        "properties": dict(entity),
                    }
                ))
            
            self.logger.debug(f"通过chunk获取实体完成: chunk_ids数量={len(chunk_ids)}, 结果数={len(results)}")
            return results
            
        except Exception as e:
            self.logger.error(f"通过chunk获取实体失败: {e}")
            return []
    
    def _generate_path_explanation(self, nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
        """
        生成路径说明文本
        
        Args:
            nodes: 路径节点列表
            relationships: 路径关系列表
            
        Returns:
            str: 路径说明
        """
        if len(nodes) < 2:
            return "空路径"
        
        explanation_parts = []
        
        for i in range(len(nodes) - 1):
            node = nodes[i]
            next_node = nodes[i + 1]
            rel = relationships[i] if i < len(relationships) else {"type": "RELATED"}
            
            node_desc = f"{node['type']}({node['name']})"
            rel_desc = rel['type']
            next_node_desc = f"{next_node['type']}({next_node['name']})"
            
            explanation_parts.append(f"{node_desc}-[{rel_desc}]->{next_node_desc}")
        
        return " → ".join(explanation_parts)
    
    def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: Neo4j服务是否健康
        """
        try:
            result = self._client.execute_cypher("RETURN 1 as test")
            return len(result) > 0
        except Exception as e:
            self.logger.error(f"Neo4j健康检查失败: {e}")
            return False