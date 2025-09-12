#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档和块的Neo4j存储服务

实现文档节点、块节点和MENTIONS关系的管理
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from ....domain.kg.schemas import DocumentDict, ChunkDict
from ....infrastructure.graph_store.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class DocumentKGStore:
    """文档和块的知识图谱存储"""
    
    def __init__(self, neo4j_client: Neo4jClient):
        self.client = neo4j_client
        self.logger = logging.getLogger(__name__)
    
    def create_document_node(self, doc_data: DocumentDict) -> bool:
        """
        创建文档节点
        
        Args:
            doc_data: 文档数据
            
        Returns:
            bool: 是否创建成功
        """
        try:
            cypher = """
            MERGE (d:Document {id: $id})
            SET d.filename = $filename,
                d.filepath = $filepath,
                d.content_type = $content_type,
                d.size = $size,
                d.checksum = $checksum,
                d.metadata = $metadata,
                d.indexed_at = $indexed_at,
                d.created_at = $created_at,
                d.updated_at = datetime()
            RETURN d.id as doc_id
            """
            
            params = {
                "id": doc_data["id"],
                "filename": doc_data["filename"],
                "filepath": doc_data["filepath"],
                "content_type": doc_data["content_type"],
                "size": doc_data["size"],
                "checksum": doc_data["checksum"],
                "metadata": doc_data["metadata"],
                "indexed_at": doc_data.get("indexed_at"),
                "created_at": doc_data.get("created_at") or datetime.now().isoformat()
            }
            
            result = self.client.execute_cypher(cypher, params)
            
            if result:
                self.logger.info(f"文档节点创建成功: {doc_data['id']}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"创建文档节点失败: {e}")
            return False
    
    def create_chunk_node(self, chunk_data: ChunkDict) -> bool:
        """
        创建块节点
        
        Args:
            chunk_data: 块数据
            
        Returns:
            bool: 是否创建成功
        """
        try:
            cypher = """
            MERGE (c:Chunk {id: $id})
            SET c.doc_id = $doc_id,
                c.chunk_index = $chunk_index,
                c.content = $content,
                c.content_hash = $content_hash,
                c.start_char = $start_char,
                c.end_char = $end_char,
                c.vector_id = $vector_id,
                c.metadata = $metadata,
                c.created_at = $created_at,
                c.updated_at = datetime()
            RETURN c.id as chunk_id
            """
            
            params = {
                "id": chunk_data["id"],
                "doc_id": chunk_data["doc_id"],
                "chunk_index": chunk_data["chunk_index"],
                "content": chunk_data["content"],
                "content_hash": chunk_data["content_hash"],
                "start_char": chunk_data["start_char"],
                "end_char": chunk_data["end_char"],
                "vector_id": chunk_data.get("vector_id"),
                "metadata": chunk_data["metadata"],
                "created_at": chunk_data.get("created_at") or datetime.now().isoformat()
            }
            
            result = self.client.execute_cypher(cypher, params)
            
            if result:
                self.logger.info(f"块节点创建成功: {chunk_data['id']}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"创建块节点失败: {e}")
            return False
    
    def create_doc_chunk_relationship(self, doc_id: str, chunk_id: str) -> bool:
        """
        创建文档-块关系
        
        Args:
            doc_id: 文档ID
            chunk_id: 块ID
            
        Returns:
            bool: 是否创建成功
        """
        try:
            cypher = """
            MATCH (d:Document {id: $doc_id})
            MATCH (c:Chunk {id: $chunk_id})
            MERGE (d)-[r:HAS_CHUNK]->(c)
            SET r.created_at = datetime()
            RETURN type(r) as rel_type
            """
            
            params = {"doc_id": doc_id, "chunk_id": chunk_id}
            result = self.client.execute_cypher(cypher, params)
            
            if result:
                self.logger.debug(f"文档-块关系创建成功: {doc_id} -> {chunk_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"创建文档-块关系失败: {e}")
            return False
    
    def create_chunk_entity_mentions(self, chunk_id: str, entity_ids: List[str], 
                                   confidence_scores: Optional[List[float]] = None) -> int:
        """
        创建块-实体MENTIONS关系
        
        Args:
            chunk_id: 块ID
            entity_ids: 实体ID列表
            confidence_scores: 置信度分数列表
            
        Returns:
            int: 成功创建的关系数量
        """
        if not entity_ids:
            return 0
        
        try:
            created_count = 0
            
            for i, entity_id in enumerate(entity_ids):
                confidence = confidence_scores[i] if confidence_scores and i < len(confidence_scores) else 0.8
                
                cypher = """
                MATCH (c:Chunk {id: $chunk_id})
                MATCH (e:Entity {id: $entity_id})
                MERGE (c)-[r:MENTIONS]->(e)
                SET r.confidence = $confidence,
                    r.created_at = datetime()
                RETURN type(r) as rel_type
                """
                
                params = {
                    "chunk_id": chunk_id,
                    "entity_id": entity_id,
                    "confidence": confidence
                }
                
                result = self.client.execute_cypher(cypher, params)
                if result:
                    created_count += 1
            
            self.logger.info(f"创建了 {created_count}/{len(entity_ids)} 个MENTIONS关系")
            return created_count
            
        except Exception as e:
            self.logger.error(f"创建MENTIONS关系失败: {e}")
            return 0
    
    def find_chunks_by_entities(self, entity_ids: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        根据实体查找相关块
        
        Args:
            entity_ids: 实体ID列表
            limit: 返回结果限制
            
        Returns:
            List[Dict]: 块信息列表
        """
        try:
            cypher = """
            MATCH (e:Entity)-[:MENTIONS]-(c:Chunk)
            WHERE e.id IN $entity_ids
            RETURN DISTINCT c.id as chunk_id, 
                   c.content as content,
                   c.metadata as metadata,
                   c.vector_id as vector_id,
                   count(e) as entity_mentions
            ORDER BY entity_mentions DESC
            LIMIT $limit
            """
            
            params = {"entity_ids": entity_ids, "limit": limit}
            result = self.client.execute_cypher(cypher, params)
            
            return result or []
            
        except Exception as e:
            self.logger.error(f"查找实体相关块失败: {e}")
            return []
    
    def find_entities_by_chunk(self, chunk_id: str) -> List[Dict[str, Any]]:
        """
        根据块查找提及的实体
        
        Args:
            chunk_id: 块ID
            
        Returns:
            List[Dict]: 实体信息列表
        """
        try:
            cypher = """
            MATCH (c:Chunk {id: $chunk_id})-[r:MENTIONS]->(e:Entity)
            RETURN e.id as entity_id,
                   e.name as entity_name,
                   e.type as entity_type,
                   r.confidence as confidence
            ORDER BY r.confidence DESC
            """
            
            params = {"chunk_id": chunk_id}
            result = self.client.execute_cypher(cypher, params)
            
            return result or []
            
        except Exception as e:
            self.logger.error(f"查找块提及实体失败: {e}")
            return []
    
    def get_chunk_context_graph(self, chunk_id: str, hop: int = 2) -> Dict[str, Any]:
        """
        获取块的上下文知识图谱
        
        Args:
            chunk_id: 块ID
            hop: 图遍历跳数
            
        Returns:
            Dict: 上下文图谱数据
        """
        try:
            cypher = f"""
            MATCH (c:Chunk {{id: $chunk_id}})
            CALL {{
                WITH c
                MATCH path = (c)-[:MENTIONS*1..{hop}]-(related)
                RETURN path
            }}
            WITH collect(path) as paths
            CALL apoc.convert.toTree(paths) yield value
            RETURN value as context_graph
            """
            
            params = {"chunk_id": chunk_id}
            result = self.client.execute_cypher(cypher, params)
            
            if result and result[0]:
                return result[0]["context_graph"]
            return {}
            
        except Exception as e:
            self.logger.warning(f"获取块上下文图谱失败 (可能需要APOC插件): {e}")
            # 降级到简单查询
            return self._get_simple_chunk_context(chunk_id, hop)
    
    def _get_simple_chunk_context(self, chunk_id: str, hop: int = 2) -> Dict[str, Any]:
        """简单的块上下文查询（不依赖APOC）"""
        try:
            cypher = """
            MATCH (c:Chunk {id: $chunk_id})-[:MENTIONS]->(e:Entity)
            OPTIONAL MATCH (e)-[r:RELATED_TO|PART_OF|INSTANCE_OF]-(related:Entity)
            RETURN c.id as chunk_id,
                   collect(DISTINCT {
                       id: e.id, 
                       name: e.name, 
                       type: e.type
                   }) as mentioned_entities,
                   collect(DISTINCT {
                       id: related.id, 
                       name: related.name, 
                       type: related.type
                   }) as related_entities
            """
            
            params = {"chunk_id": chunk_id}
            result = self.client.execute_cypher(cypher, params)
            
            return result[0] if result else {}
            
        except Exception as e:
            self.logger.error(f"获取简单块上下文失败: {e}")
            return {}