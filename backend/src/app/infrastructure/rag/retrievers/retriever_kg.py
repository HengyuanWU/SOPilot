#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG Retriever - 知识图谱检索器

基于Neo4j的知识图谱检索功能
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..kgstores.neo4j_queries import Neo4jKGQueries, KGSearchResult

logger = logging.getLogger(__name__)


@dataclass
class KGRetrievalResult:
    """KG检索结果"""
    type: str  # "entity", "path", "subgraph"
    score: float
    content: str  # 可读的内容描述
    data: Dict[str, Any]  # 原始数据
    explanation: Optional[str] = None


class KGRetriever:
    """知识图谱检索器"""
    
    def __init__(self, neo4j_queries: Neo4jKGQueries):
        """
        初始化KG检索器
        
        Args:
            neo4j_queries: Neo4j查询实例
        """
        self.neo4j_queries = neo4j_queries
        self.logger = logging.getLogger(__name__)
    
    def search(self, query: str, top_k: int = 8, hop: int = 2, 
               rel_types: List[str] = None, scope: str = None) -> List[KGRetrievalResult]:
        """
        知识图谱检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            hop: 图遍历跳数
            rel_types: 关系类型过滤
            scope: 范围过滤（如book_id）
            
        Returns:
            List[KGRetrievalResult]: 检索结果
        """
        try:
            self.logger.debug(f"开始KG检索: query='{query[:50]}...', top_k={top_k}, hop={hop}")
            
            all_results = []
            
            # 1. 实体搜索
            entity_results = self._search_entities(query, top_k=top_k//2, scope=scope)
            all_results.extend(entity_results)
            
            # 2. 如果找到了实体，进行子图扩展
            if entity_results and hop > 0:
                subgraph_results = self._expand_subgraphs(entity_results, hop=hop, 
                                                        rel_types=rel_types, 
                                                        limit=top_k//2)
                all_results.extend(subgraph_results)
            
            # 3. 按分数排序并限制结果数量
            all_results.sort(key=lambda x: x.score, reverse=True)
            results = all_results[:top_k]
            
            self.logger.info(f"KG检索完成: 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"KG检索失败: {e}")
            return []
    
    def search_entities(self, query: str, entity_types: List[str] = None, 
                       top_k: int = 10, scope: str = None) -> List[KGRetrievalResult]:
        """
        搜索实体
        
        Args:
            query: 搜索查询
            entity_types: 实体类型过滤
            top_k: 结果数量
            scope: 范围过滤
            
        Returns:
            List[KGRetrievalResult]: 实体结果
        """
        return self._search_entities(query, entity_types, top_k, scope)
    
    def get_subgraph(self, entity_name: str, hop: int = 2, rel_types: List[str] = None, 
                    limit: int = 20) -> List[KGRetrievalResult]:
        """
        获取实体子图
        
        Args:
            entity_name: 实体名称
            hop: 跳数
            rel_types: 关系类型过滤
            limit: 结果数量限制
            
        Returns:
            List[KGRetrievalResult]: 子图结果
        """
        try:
            # 首先查找实体
            entity_results = self._search_entities(entity_name, top_k=1)
            if not entity_results:
                self.logger.warning(f"未找到实体: {entity_name}")
                return []
            
            entity_id = entity_results[0].data.get("id")
            if not entity_id:
                self.logger.warning(f"实体缺少ID: {entity_name}")
                return []
            
            # 获取子图
            kg_results = self.neo4j_queries.get_entity_subgraph(
                entity_id=entity_id,
                hop=hop,
                rel_types=rel_types,
                limit=limit
            )
            
            # 转换结果格式
            results = []
            for kg_result in kg_results:
                content = self._format_subgraph_content(kg_result.data)
                
                results.append(KGRetrievalResult(
                    type="subgraph",
                    score=kg_result.score,
                    content=content,
                    data=kg_result.data,
                    explanation=kg_result.explanation
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"获取子图失败: {e}")
            return []
    
    def find_path(self, start_entity: str, end_entity: str, max_hop: int = 3, 
                  rel_types: List[str] = None) -> List[KGRetrievalResult]:
        """
        查找实体间路径
        
        Args:
            start_entity: 起始实体
            end_entity: 目标实体
            max_hop: 最大跳数
            rel_types: 关系类型过滤
            
        Returns:
            List[KGRetrievalResult]: 路径结果
        """
        try:
            kg_results = self.neo4j_queries.find_shortest_path(
                start_entity=start_entity,
                end_entity=end_entity,
                max_hop=max_hop,
                rel_types=rel_types
            )
            
            results = []
            for kg_result in kg_results:
                content = self._format_path_content(kg_result.data)
                
                results.append(KGRetrievalResult(
                    type="path",
                    score=kg_result.score,
                    content=content,
                    data=kg_result.data,
                    explanation=kg_result.explanation
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"查找路径失败: {e}")
            return []
    
    def get_entities_by_chunks(self, chunk_ids: List[str], top_k: int = 10) -> List[KGRetrievalResult]:
        """
        根据文档块获取相关实体
        
        Args:
            chunk_ids: 文档块ID列表
            top_k: 结果数量
            
        Returns:
            List[KGRetrievalResult]: 相关实体结果
        """
        try:
            kg_results = self.neo4j_queries.get_entities_by_chunks(chunk_ids)
            
            results = []
            for kg_result in kg_results[:top_k]:
                content = self._format_entity_content(kg_result.data)
                
                results.append(KGRetrievalResult(
                    type="entity",
                    score=kg_result.score,
                    content=content,
                    data=kg_result.data
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"根据chunk获取实体失败: {e}")
            return []
    
    def _search_entities(self, query: str, entity_types: List[str] = None, 
                        top_k: int = 10, scope: str = None) -> List[KGRetrievalResult]:
        """内部实体搜索方法"""
        try:
            kg_results = self.neo4j_queries.search_entities(
                query=query,
                entity_types=entity_types,
                limit=top_k,
                scope=scope
            )
            
            results = []
            for kg_result in kg_results:
                content = self._format_entity_content(kg_result.data)
                
                results.append(KGRetrievalResult(
                    type="entity",
                    score=kg_result.score,
                    content=content,
                    data=kg_result.data
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"实体搜索失败: {e}")
            return []
    
    def _expand_subgraphs(self, entity_results: List[KGRetrievalResult], hop: int = 2, 
                         rel_types: List[str] = None, limit: int = 10) -> List[KGRetrievalResult]:
        """扩展实体的子图"""
        try:
            subgraph_results = []
            
            for entity_result in entity_results[:3]:  # 只对前3个实体扩展子图
                entity_id = entity_result.data.get("id")
                if not entity_id:
                    continue
                
                kg_results = self.neo4j_queries.get_entity_subgraph(
                    entity_id=entity_id,
                    hop=hop,
                    rel_types=rel_types,
                    limit=limit
                )
                
                for kg_result in kg_results:
                    content = self._format_subgraph_content(kg_result.data)
                    
                    subgraph_results.append(KGRetrievalResult(
                        type="subgraph",
                        score=kg_result.score * 0.8,  # 子图分数略微降权
                        content=content,
                        data=kg_result.data,
                        explanation=kg_result.explanation
                    ))
            
            return subgraph_results
            
        except Exception as e:
            self.logger.error(f"扩展子图失败: {e}")
            return []
    
    def _format_entity_content(self, entity_data: Dict[str, Any]) -> str:
        """格式化实体内容为可读文本"""
        name = entity_data.get("name", "未知实体")
        entity_type = entity_data.get("type", "实体")
        desc = entity_data.get("desc", "")
        
        content_parts = [f"{entity_type}: {name}"]
        if desc:
            content_parts.append(f"描述: {desc}")
        
        return " | ".join(content_parts)
    
    def _format_path_content(self, path_data: Dict[str, Any]) -> str:
        """格式化路径内容为可读文本"""
        nodes = path_data.get("nodes", [])
        relationships = path_data.get("relationships", [])
        
        if len(nodes) < 2:
            return "空路径"
        
        path_parts = []
        for i in range(len(nodes) - 1):
            node = nodes[i]
            next_node = nodes[i + 1]
            rel = relationships[i] if i < len(relationships) else {"type": "相关"}
            
            node_name = node.get("name", "未知")
            rel_type = rel.get("type", "相关")
            next_node_name = next_node.get("name", "未知")
            
            path_parts.append(f"{node_name} -{rel_type}-> {next_node_name}")
        
        return " → ".join(path_parts)
    
    def _format_subgraph_content(self, subgraph_data: Dict[str, Any]) -> str:
        """格式化子图内容为可读文本"""
        nodes = subgraph_data.get("nodes", [])
        relationships = subgraph_data.get("relationships", [])
        path_length = subgraph_data.get("path_length", 0)
        
        if not nodes:
            return "空子图"
        
        # 提取主要实体
        main_entities = [node.get("name", "未知") for node in nodes[:3]]
        
        # 提取主要关系
        main_relations = list(set(rel.get("type", "相关") for rel in relationships[:3]))
        
        content = f"子图({path_length}跳): {', '.join(main_entities)}"
        if main_relations:
            content += f" | 关系: {', '.join(main_relations)}"
        
        return content
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取检索器统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            is_healthy = self.neo4j_queries.health_check()
            
            return {
                "neo4j_status": "healthy" if is_healthy else "unhealthy",
                "supported_operations": [
                    "entity_search",
                    "subgraph_query", 
                    "path_finding",
                    "chunk_entity_mapping"
                ]
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"status": "error", "error": str(e)}