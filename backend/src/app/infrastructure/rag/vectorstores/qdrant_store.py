#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qdrant Store - Qdrant向量数据库封装

提供Qdrant集合管理、批量upsert、向量检索等功能
"""

import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """向量搜索结果"""
    id: str
    score: float
    payload: Dict[str, Any]
    vector: Optional[List[float]] = None


class QdrantStore:
    """Qdrant向量存储封装"""
    
    def __init__(self, url: str = "http://localhost:6333", api_key: Optional[str] = None, collection_name: str = "kb_chunks"):
        """
        初始化Qdrant客户端
        
        Args:
            url: Qdrant服务URL
            api_key: API密钥（可选）
            collection_name: 集合名称
        """
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.logger = logging.getLogger(__name__)
        
        self._client = None
        self._connect()
    
    def _connect(self):
        """连接到Qdrant服务"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
            
            self._client = QdrantClient(url=self.url, api_key=self.api_key)
            self._Distance = Distance
            self._VectorParams = VectorParams
            self._PointStruct = PointStruct
            
            self.logger.info(f"成功连接到Qdrant: {self.url}")
            
        except ImportError:
            raise ImportError("需要安装qdrant-client: pip install qdrant-client")
        except Exception as e:
            self.logger.error(f"连接Qdrant失败: {e}")
            raise
    
    def _ensure_collection_exists(self):
        """确保集合存在，如果不存在则创建"""
        try:
            # 检查集合是否存在
            collections = self._client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                self.logger.info(f"集合 {self.collection_name} 不存在，自动创建...")
                # 使用默认向量维度创建集合（可以从配置获取）
                default_vector_size = 768  # 常见的embedding维度
                self.create_collection(vector_size=default_vector_size, distance="cosine")
                
        except Exception as e:
            self.logger.warning(f"检查/创建集合失败: {e}")
    
    def create_collection(self, vector_size: int, distance: str = "cosine", force_recreate: bool = False) -> bool:
        """
        创建集合
        
        Args:
            vector_size: 向量维度
            distance: 距离度量 ("cosine", "euclidean", "dot")
            force_recreate: 是否强制重新创建
            
        Returns:
            bool: 创建是否成功
        """
        try:
            # 检查集合是否存在
            collections = self._client.get_collections().collections
            collection_exists = any(col.name == self.collection_name for col in collections)
            
            if collection_exists:
                if force_recreate:
                    self.logger.info(f"删除现有集合: {self.collection_name}")
                    self._client.delete_collection(self.collection_name)
                else:
                    self.logger.info(f"集合已存在: {self.collection_name}")
                    return True
            
            # 距离度量映射
            distance_map = {
                "cosine": self._Distance.COSINE,
                "euclidean": self._Distance.EUCLID,
                "dot": self._Distance.DOT,
            }
            
            if distance not in distance_map:
                raise ValueError(f"不支持的距离度量: {distance}")
            
            # 创建集合
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=self._VectorParams(
                    size=vector_size,
                    distance=distance_map[distance]
                )
            )
            
            self.logger.info(f"成功创建集合: {self.collection_name} (dim={vector_size}, distance={distance})")
            return True
            
        except Exception as e:
            self.logger.error(f"创建集合失败: {e}")
            return False
    
    def upsert_vectors(self, documents: List[Dict[str, Any]], vector_field: str = "vector", id_field: str = "chunk_id") -> bool:
        """
        批量插入或更新向量
        
        Args:
            documents: 文档列表，包含向量和元数据
            vector_field: 向量字段名
            id_field: ID字段名
            
        Returns:
            bool: 操作是否成功
        """
        if not documents:
            return True
        
        try:
            points = []
            for doc in documents:
                if vector_field not in doc:
                    self.logger.warning(f"文档缺少向量字段: {vector_field}")
                    continue
                
                # 生成ID（如果没有提供）
                point_id = doc.get(id_field) or str(uuid.uuid4())
                
                # 构建payload（排除向量字段）
                payload = {k: v for k, v in doc.items() if k != vector_field}
                payload["created_at"] = datetime.now().isoformat()
                
                # 创建Point
                point = self._PointStruct(
                    id=point_id,
                    vector=doc[vector_field],
                    payload=payload
                )
                points.append(point)
            
            # 批量upsert
            self._client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            self.logger.info(f"成功upsert {len(points)} 个向量到集合: {self.collection_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"upsert向量失败: {e}")
            return False
    
    def search_vectors(self, query_vector: List[float], top_k: int = 10, score_threshold: Optional[float] = None, 
                      filters: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        """
        向量搜索
        
        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            score_threshold: 分数阈值
            filters: 过滤条件
            
        Returns:
            List[VectorSearchResult]: 搜索结果
        """
        try:
            # 确保集合存在
            self._ensure_collection_exists()
            
            # 构建搜索条件
            search_params = {
                "collection_name": self.collection_name,
                "query_vector": query_vector,
                "limit": top_k,
                "with_payload": True,
                "with_vectors": False,
            }
            
            if score_threshold is not None:
                search_params["score_threshold"] = score_threshold
                
            if filters:
                # TODO: 实现Qdrant过滤器格式转换
                pass
            
            # 执行搜索
            search_results = self._client.search(**search_params)
            
            # 转换结果格式
            results = []
            for result in search_results:
                results.append(VectorSearchResult(
                    id=str(result.id),
                    score=result.score,
                    payload=result.payload or {}
                ))
            
            self.logger.debug(f"向量搜索完成: 查询维度={len(query_vector)}, 返回结果={len(results)}")
            return results
            
        except Exception as e:
            self.logger.error(f"向量搜索失败: {e}")
            return []
    
    def get_by_id(self, point_id: str) -> Optional[VectorSearchResult]:
        """
        根据ID获取向量点
        
        Args:
            point_id: 点ID
            
        Returns:
            Optional[VectorSearchResult]: 搜索结果
        """
        try:
            points = self._client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=True
            )
            
            if not points:
                return None
            
            point = points[0]
            return VectorSearchResult(
                id=str(point.id),
                score=1.0,  # 精确匹配
                payload=point.payload or {},
                vector=point.vector
            )
            
        except Exception as e:
            self.logger.error(f"根据ID获取向量失败: {e}")
            return None
    
    def delete_by_ids(self, point_ids: List[str]) -> bool:
        """
        根据ID列表删除向量点
        
        Args:
            point_ids: 点ID列表
            
        Returns:
            bool: 删除是否成功
        """
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=point_ids
            )
            
            self.logger.info(f"成功删除 {len(point_ids)} 个向量点")
            return True
            
        except Exception as e:
            self.logger.error(f"删除向量点失败: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        获取集合信息
        
        Returns:
            Dict[str, Any]: 集合信息
        """
        try:
            info = self._client.get_collection(self.collection_name)
            return {
                "name": info.config.params.vectors.size if hasattr(info.config.params, 'vectors') else 0,
                "vector_size": info.config.params.vectors.size if hasattr(info.config.params, 'vectors') else 0,
                "distance": str(info.config.params.vectors.distance) if hasattr(info.config.params, 'vectors') else "unknown",
                "points_count": info.points_count,
                "segments_count": info.segments_count,
                "disk_data_size": info.disk_data_size,
                "ram_data_size": info.ram_data_size,
            }
        except Exception as e:
            self.logger.error(f"获取集合信息失败: {e}")
            return {}
    
    def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: 服务是否健康
        """
        try:
            # 尝试获取集合列表
            collections = self._client.get_collections()
            return True
        except Exception as e:
            self.logger.error(f"Qdrant健康检查失败: {e}")
            return False