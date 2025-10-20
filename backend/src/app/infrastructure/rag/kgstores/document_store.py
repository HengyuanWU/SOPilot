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
from ....domain.kg.models import Doc, Chunk as ChunkNode, Entity
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
            # 使用 neomodel Doc 模型合併/更新
            doc_id = doc_data["id"]
            props = {
                "id": doc_id,
                "name": doc_data.get("filename") or Path(doc_data.get("filepath", "")).name,
                "type": "Document",
                "filename": doc_data.get("filename"),
                "filepath": doc_data.get("filepath"),
                "content_type": doc_data.get("content_type"),
                "size": doc_data.get("size"),
                "checksum": doc_data.get("checksum"),
                "metadata": doc_data.get("metadata"),
                "indexed_at": doc_data.get("indexed_at"),
                "scope": doc_data.get("scope"),
            }

            node = Doc.nodes.get_or_none(id=doc_id)
            if node is None:
                node = Doc(**props)
            else:
                for k, v in props.items():
                    setattr(node, k, v)
            node.save()

            self.logger.info(f"文档节点创建成功: {doc_id}")
            return True
            
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
            chunk_id = chunk_data["id"]
            props = {
                "id": chunk_id,
                "name": f"chunk-{chunk_data.get('chunk_index', 0)}",
                "type": "Chunk",
                "doc_id": chunk_data.get("doc_id"),
                "chunk_index": chunk_data.get("chunk_index"),
                "content": chunk_data.get("content"),
                "content_hash": chunk_data.get("content_hash"),
                "start_char": chunk_data.get("start_char"),
                "end_char": chunk_data.get("end_char"),
                "vector_id": chunk_data.get("vector_id"),
                "metadata": chunk_data.get("metadata"),
                "scope": chunk_data.get("scope"),
            }

            node = ChunkNode.nodes.get_or_none(id=chunk_id)
            if node is None:
                node = ChunkNode(**props)
            else:
                for k, v in props.items():
                    setattr(node, k, v)
            node.save()

            self.logger.info(f"块节点创建成功: {chunk_id}")
            return True
            
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
            d = Doc.nodes.get_or_none(id=doc_id)
            c = ChunkNode.nodes.get_or_none(id=chunk_id)
            if not d or not c:
                return False
            # 建立關係（無屬性）
            d.chunks.connect(c)
            self.logger.debug(f"文档-块关系创建成功: {doc_id} -> {chunk_id}")
            return True
            
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
            
            cnode = ChunkNode.nodes.get_or_none(id=chunk_id)
            if not cnode:
                return 0
            for i, entity_id in enumerate(entity_ids):
                confidence = confidence_scores[i] if confidence_scores and i < len(confidence_scores) else 0.8
                enode = Entity.nodes.get_or_none(id=entity_id)
                if not enode:
                    continue
                # 使用帶 KGRel 的 mentions 關係，填充必要欄位
                rel = cnode.mentions.relationship(enode)
                if rel is None:
                    cnode.mentions.connect(enode, {
                        "rid": f"MENTIONS:{chunk_id}->{entity_id}",
                        "type": "MENTIONS",
                        "src": chunk_id,  # 源可後續改為 section_id
                        "scope": cnode.scope or "",
                        "confidence": float(confidence),
                        "weight": 1.0,
                        "evidence": chunk_id,
                    })
                else:
                    rel.confidence = float(confidence)
                    rel.save()
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
            # 使用 neomodel 查找（回退到 Cypher 如需更高效可再優化）
            results: List[Dict[str, Any]] = []
            for eid in entity_ids:
                enode = Entity.nodes.get_or_none(id=eid)
                if not enode:
                    continue
                # 反向遍歷 mentions 關係：被某實體提及的 chunks
                rels = enode.inbound_relationships.relationship_model
                # 簡化：用 Cypher 更高效
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
            result = self.client.execute_cypher(cypher, params)  # 查詢類，保留原接口
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
            # 直接通過關係遍歷以獲取屬性，為保持輸出結構，組裝字典
            cnode = ChunkNode.nodes.get_or_none(id=chunk_id)
            if not cnode:
                return []
            rows: List[Dict[str, Any]] = []
            for enode in cnode.mentions:
                rel = cnode.mentions.relationship(enode)
                rows.append({
                    "entity_id": enode.id,
                    "entity_name": enode.name,
                    "entity_type": enode.type,
                    "confidence": getattr(rel, "confidence", 0.8),
                })
            rows.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            return rows
            
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
            # 複雜遍歷仍保留 Cypher（查詢類）
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