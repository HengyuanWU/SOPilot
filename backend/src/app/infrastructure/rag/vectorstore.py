#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangChain VectorStore Integration - 向量存储 LangChain 集成

提供基于 LangChain 的 Qdrant 向量存储集成：
1. 使用 LangChain Qdrant 标准接口
2. 与自定义 Embeddings 集成
3. 支持元数据过滤和混合搜索
4. 保持与现有系统的兼容性
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import uuid

from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


@dataclass
class VectorStoreConfig:
    """向量存储配置"""
    url: str = "http://localhost:6333"
    api_key: Optional[str] = None
    collection_name: str = "kb_chunks"
    distance: str = "cosine"  # "cosine", "euclidean", "dot"


class LangChainQdrantStore:
    """
    LangChain Qdrant 向量存储封装
    
    使用 LangChain 的标准 Qdrant 集成，提供：
    - 统一的 VectorStore 接口
    - 文档存储和检索
    - 元数据过滤
    - 相似度搜索
    """
    
    def __init__(
        self,
        embeddings: Embeddings,
        config: Optional[VectorStoreConfig] = None,
        **kwargs
    ):
        """
        初始化 LangChain Qdrant 存储
        
        Args:
            embeddings: LangChain Embeddings 实例
            config: 向量存储配置
            **kwargs: 额外的 Qdrant 配置参数
        """
        self.embeddings = embeddings
        self.config = config or VectorStoreConfig()
        self.logger = logging.getLogger(__name__)
        
        # 合并配置
        self._qdrant_config = {
            "url": self.config.url,
            "api_key": self.config.api_key,
            "collection_name": self.config.collection_name,
            **kwargs
        }
        
        # 延迟初始化 vectorstore
        self._vectorstore = None
        self._client = None
    
    def _ensure_vectorstore(self):
        """确保 vectorstore 已初始化"""
        if self._vectorstore is not None:
            return
        
        try:
            from langchain_community.vectorstores import Qdrant
            from qdrant_client import QdrantClient
            
            # 创建 Qdrant 客户端
            self._client = QdrantClient(
                url=self.config.url,
                api_key=self.config.api_key
            )
            
            # 检查集合是否存在
            collections = self._client.get_collections()
            collection_exists = any(
                col.name == self.config.collection_name 
                for col in collections.collections
            )
            
            if collection_exists:
                # 从现有集合加载
                self._vectorstore = Qdrant(
                    client=self._client,
                    collection_name=self.config.collection_name,
                    embeddings=self.embeddings
                )
                self.logger.info(f"加载现有集合: {self.config.collection_name}")
            else:
                # 集合不存在，需要先创建
                self.logger.warning(
                    f"集合 {self.config.collection_name} 不存在。"
                    "请先使用 create_collection() 创建。"
                )
                # 仍然初始化 vectorstore，但在使用时可能会失败
                self._vectorstore = Qdrant(
                    client=self._client,
                    collection_name=self.config.collection_name,
                    embeddings=self.embeddings
                )
            
        except ImportError:
            raise ImportError(
                "需要安装 langchain-community: pip install langchain-community"
            )
        except Exception as e:
            self.logger.error(f"初始化 Qdrant vectorstore 失败: {e}")
            raise
    
    def create_collection(
        self,
        vector_size: Optional[int] = None,
        force_recreate: bool = False
    ) -> bool:
        """
        创建集合
        
        Args:
            vector_size: 向量维度（None = 从 embeddings 推断）
            force_recreate: 是否强制重新创建
            
        Returns:
            bool: 创建是否成功
        """
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            # 创建客户端
            if self._client is None:
                self._client = QdrantClient(
                    url=self.config.url,
                    api_key=self.config.api_key
                )
            
            # 推断向量维度
            if vector_size is None:
                if hasattr(self.embeddings, 'dimension'):
                    vector_size = self.embeddings.dimension
                else:
                    # 通过嵌入一个示例文本来推断维度
                    test_vector = self.embeddings.embed_query("test")
                    vector_size = len(test_vector)
            
            # 检查集合是否存在
            collections = self._client.get_collections().collections
            collection_exists = any(
                col.name == self.config.collection_name 
                for col in collections
            )
            
            if collection_exists:
                if force_recreate:
                    self.logger.info(f"删除现有集合: {self.config.collection_name}")
                    self._client.delete_collection(self.config.collection_name)
                else:
                    self.logger.info(f"集合已存在: {self.config.collection_name}")
                    return True
            
            # 距离度量映射
            distance_map = {
                "cosine": Distance.COSINE,
                "euclidean": Distance.EUCLID,
                "dot": Distance.DOT,
            }
            
            distance_metric = distance_map.get(
                self.config.distance, 
                Distance.COSINE
            )
            
            # 创建集合
            self._client.create_collection(
                collection_name=self.config.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance_metric
                )
            )
            
            self.logger.info(
                f"成功创建集合: {self.config.collection_name} "
                f"(dim={vector_size}, distance={self.config.distance})"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"创建集合失败: {e}")
            return False
    
    def add_documents(
        self,
        documents: List[Document],
        ids: Optional[List[str]] = None,
        batch_size: int = 32
    ) -> List[str]:
        """
        添加文档到向量存储
        
        Args:
            documents: LangChain Document 列表
            ids: 文档 ID 列表（None = 自动生成）
            batch_size: 批处理大小
            
        Returns:
            List[str]: 文档 ID 列表
        """
        self._ensure_vectorstore()
        
        try:
            # 生成 IDs（如果未提供）
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in documents]
            
            self.logger.info(f"添加 {len(documents)} 个文档到向量存储")
            
            # 批量添加
            result_ids = self._vectorstore.add_documents(
                documents=documents,
                ids=ids,
                batch_size=batch_size
            )
            
            self.logger.info(f"成功添加 {len(result_ids)} 个文档")
            return result_ids
            
        except Exception as e:
            self.logger.error(f"添加文档失败: {e}")
            raise
    
    def similarity_search(
        self,
        query: str,
        k: int = 10,
        score_threshold: Optional[float] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        相似度搜索
        
        Args:
            query: 查询文本
            k: 返回结果数量
            score_threshold: 分数阈值
            filter: 元数据过滤条件
            
        Returns:
            List[Document]: 搜索结果文档
        """
        self._ensure_vectorstore()
        
        try:
            self.logger.debug(f"相似度搜索: query='{query[:50]}...', k={k}")
            
            # 构建搜索参数
            search_kwargs = {"k": k}
            if score_threshold is not None:
                search_kwargs["score_threshold"] = score_threshold
            if filter is not None:
                search_kwargs["filter"] = filter
            
            # 执行搜索
            results = self._vectorstore.similarity_search(
                query=query,
                **search_kwargs
            )
            
            self.logger.info(f"搜索完成: 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"相似度搜索失败: {e}")
            return []
    
    def similarity_search_with_score(
        self,
        query: str,
        k: int = 10,
        score_threshold: Optional[float] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        """
        带分数的相似度搜索
        
        Args:
            query: 查询文本
            k: 返回结果数量
            score_threshold: 分数阈值
            filter: 元数据过滤条件
            
        Returns:
            List[Tuple[Document, float]]: (文档, 分数) 元组列表
        """
        self._ensure_vectorstore()
        
        try:
            self.logger.debug(f"带分数搜索: query='{query[:50]}...', k={k}")
            
            # 构建搜索参数
            search_kwargs = {"k": k}
            if score_threshold is not None:
                search_kwargs["score_threshold"] = score_threshold
            if filter is not None:
                search_kwargs["filter"] = filter
            
            # 执行搜索
            results = self._vectorstore.similarity_search_with_score(
                query=query,
                **search_kwargs
            )
            
            self.logger.info(f"带分数搜索完成: 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"带分数搜索失败: {e}")
            return []
    
    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 10,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        最大边际相关性搜索（MMR）
        
        平衡相关性和多样性
        
        Args:
            query: 查询文本
            k: 返回结果数量
            fetch_k: 初始获取数量
            lambda_mult: 多样性权重（0=最多样，1=最相关）
            filter: 元数据过滤条件
            
        Returns:
            List[Document]: 搜索结果文档
        """
        self._ensure_vectorstore()
        
        try:
            self.logger.debug(f"MMR 搜索: query='{query[:50]}...', k={k}")
            
            # 构建搜索参数
            search_kwargs = {
                "k": k,
                "fetch_k": fetch_k,
                "lambda_mult": lambda_mult
            }
            if filter is not None:
                search_kwargs["filter"] = filter
            
            # 执行 MMR 搜索
            results = self._vectorstore.max_marginal_relevance_search(
                query=query,
                **search_kwargs
            )
            
            self.logger.info(f"MMR 搜索完成: 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"MMR 搜索失败: {e}")
            return []
    
    def as_retriever(self, **kwargs) -> Any:
        """
        转换为 LangChain Retriever
        
        Args:
            **kwargs: Retriever 配置参数
            
        Returns:
            VectorStoreRetriever: LangChain retriever 实例
        """
        self._ensure_vectorstore()
        
        return self._vectorstore.as_retriever(**kwargs)
    
    def delete(self, ids: List[str]) -> bool:
        """
        删除文档
        
        Args:
            ids: 文档 ID 列表
            
        Returns:
            bool: 删除是否成功
        """
        self._ensure_vectorstore()
        
        try:
            self._vectorstore.delete(ids=ids)
            self.logger.info(f"成功删除 {len(ids)} 个文档")
            return True
            
        except Exception as e:
            self.logger.error(f"删除文档失败: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        获取集合信息
        
        Returns:
            Dict[str, Any]: 集合信息
        """
        try:
            if self._client is None:
                from qdrant_client import QdrantClient
                self._client = QdrantClient(
                    url=self.config.url,
                    api_key=self.config.api_key
                )
            
            info = self._client.get_collection(self.config.collection_name)
            
            # 兼容不同版本
            vectors_cfg = getattr(getattr(info.config, 'params', {}), 'vectors', None)
            
            return {
                "name": self.config.collection_name,
                "vector_size": getattr(vectors_cfg, 'size', 0) if vectors_cfg else 0,
                "distance": str(getattr(vectors_cfg, 'distance', 'unknown')) if vectors_cfg else "unknown",
                "points_count": getattr(info, 'points_count', None),
                "segments_count": getattr(info, 'segments_count', None),
                "disk_data_size": getattr(info, 'disk_data_size', None),
                "ram_data_size": getattr(info, 'ram_data_size', None),
            }
            
        except Exception as e:
            self.logger.error(f"获取集合信息失败: {e}")
            return {}
    
    @property
    def vectorstore(self):
        """获取底层 LangChain vectorstore 实例"""
        self._ensure_vectorstore()
        return self._vectorstore


def create_qdrant_store(
    embeddings: Embeddings,
    collection_name: str = "kb_chunks",
    url: str = "http://localhost:6333",
    api_key: Optional[str] = None,
    **kwargs
) -> LangChainQdrantStore:
    """
    创建 Qdrant 向量存储实例
    
    Args:
        embeddings: LangChain Embeddings 实例
        collection_name: 集合名称
        url: Qdrant 服务 URL
        api_key: API 密钥
        **kwargs: 额外配置参数
        
    Returns:
        LangChainQdrantStore: 向量存储实例
    """
    config = VectorStoreConfig(
        url=url,
        api_key=api_key,
        collection_name=collection_name
    )
    
    return LangChainQdrantStore(
        embeddings=embeddings,
        config=config,
        **kwargs
    )

