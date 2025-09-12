#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vector Retriever - 向量检索器

基于Qdrant的向量检索功能
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..vectorstores.qdrant_store import QdrantStore, VectorSearchResult
from ..embedder import Embedder

logger = logging.getLogger(__name__)


@dataclass
class VectorRetrievalResult:
    """向量检索结果"""
    chunk_id: str
    doc_id: str
    text: str
    score: float
    meta: Dict[str, Any]


class VectorRetriever:
    """向量检索器"""
    
    def __init__(self, qdrant_store: QdrantStore, embedder: Embedder):
        """
        初始化向量检索器
        
        Args:
            qdrant_store: Qdrant存储实例
            embedder: 嵌入器实例
        """
        self.qdrant_store = qdrant_store
        self.embedder = embedder
        self.logger = logging.getLogger(__name__)
    
    def search(self, query: str, top_k: int = 10, score_threshold: Optional[float] = None, 
               filters: Optional[Dict[str, Any]] = None) -> List[VectorRetrievalResult]:
        """
        向量检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            score_threshold: 分数阈值
            filters: 过滤条件
            
        Returns:
            List[VectorRetrievalResult]: 检索结果
        """
        try:
            # 1. 将查询文本转换为向量
            self.logger.debug(f"开始向量检索: query='{query[:50]}...', top_k={top_k}")
            
            query_embedding = self.embedder.embed_single(query)
            query_vector = query_embedding.vector.tolist()
            
            # 2. 在Qdrant中搜索
            search_results = self.qdrant_store.search_vectors(
                query_vector=query_vector,
                top_k=top_k,
                score_threshold=score_threshold,
                filters=filters
            )
            
            # 3. 转换结果格式
            results = []
            for result in search_results:
                payload = result.payload
                
                # 提取必要字段
                chunk_id = payload.get("chunk_id", result.id)
                doc_id = payload.get("doc_id", "unknown")
                text = payload.get("text", "")
                
                # 构建元数据（排除主要字段）
                meta = {k: v for k, v in payload.items() 
                       if k not in ["chunk_id", "doc_id", "text"]}
                
                results.append(VectorRetrievalResult(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    text=text,
                    score=result.score,
                    meta=meta
                ))
            
            self.logger.info(f"向量检索完成: 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"向量检索失败: {e}")
            return []
    
    def search_by_vector(self, query_vector: List[float], top_k: int = 10, 
                        score_threshold: Optional[float] = None, 
                        filters: Optional[Dict[str, Any]] = None) -> List[VectorRetrievalResult]:
        """
        直接使用向量进行检索
        
        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            score_threshold: 分数阈值
            filters: 过滤条件
            
        Returns:
            List[VectorRetrievalResult]: 检索结果
        """
        try:
            self.logger.debug(f"开始向量检索（直接向量）: dim={len(query_vector)}, top_k={top_k}")
            
            # 在Qdrant中搜索
            search_results = self.qdrant_store.search_vectors(
                query_vector=query_vector,
                top_k=top_k,
                score_threshold=score_threshold,
                filters=filters
            )
            
            # 转换结果格式
            results = []
            for result in search_results:
                payload = result.payload
                
                chunk_id = payload.get("chunk_id", result.id)
                doc_id = payload.get("doc_id", "unknown")
                text = payload.get("text", "")
                meta = {k: v for k, v in payload.items() 
                       if k not in ["chunk_id", "doc_id", "text"]}
                
                results.append(VectorRetrievalResult(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    text=text,
                    score=result.score,
                    meta=meta
                ))
            
            self.logger.info(f"向量检索（直接向量）完成: 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"向量检索（直接向量）失败: {e}")
            return []
    
    def search_similar_chunks(self, chunk_id: str, top_k: int = 5, exclude_self: bool = True) -> List[VectorRetrievalResult]:
        """
        查找相似的文档块
        
        Args:
            chunk_id: 参考文档块ID
            top_k: 返回结果数量
            exclude_self: 是否排除自身
            
        Returns:
            List[VectorRetrievalResult]: 相似文档块列表
        """
        try:
            # 1. 获取参考文档块的向量
            reference_point = self.qdrant_store.get_by_id(chunk_id)
            if not reference_point or not reference_point.vector:
                self.logger.warning(f"未找到文档块或向量: {chunk_id}")
                return []
            
            # 2. 使用参考向量进行搜索
            actual_top_k = top_k + 1 if exclude_self else top_k
            results = self.search_by_vector(
                query_vector=reference_point.vector,
                top_k=actual_top_k
            )
            
            # 3. 排除自身（如果需要）
            if exclude_self:
                results = [r for r in results if r.chunk_id != chunk_id]
            
            return results[:top_k]
            
        except Exception as e:
            self.logger.error(f"查找相似文档块失败: {e}")
            return []
    
    def search_by_document(self, doc_id: str, query: str, top_k: int = 5) -> List[VectorRetrievalResult]:
        """
        在指定文档中进行向量检索
        
        Args:
            doc_id: 文档ID
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            List[VectorRetrievalResult]: 检索结果
        """
        try:
            # 构建文档过滤条件
            filters = {"doc_id": doc_id}
            
            return self.search(
                query=query,
                top_k=top_k,
                filters=filters
            )
            
        except Exception as e:
            self.logger.error(f"文档内向量检索失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取检索器统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            collection_info = self.qdrant_store.get_collection_info()
            embedder_info = {
                "model_name": self.embedder.model_name,
                "dimension": self.embedder.dimension,
                "is_loaded": self.embedder.is_loaded,
            }
            
            return {
                "collection": collection_info,
                "embedder": embedder_info,
                "status": "healthy" if self.qdrant_store.health_check() else "unhealthy"
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"status": "error", "error": str(e)}