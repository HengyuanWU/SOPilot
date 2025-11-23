#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangChain Embeddings Integration - 向量嵌入 LangChain 集成

提供基于 LangChain 的 Embeddings 实现，支持：
1. OpenAI-compatible API 集成（通过 LLMRouter）
2. CacheBackedEmbeddings 持久化缓存
3. 批量嵌入优化
4. 与现有 Embedder 接口兼容
"""

import logging
from typing import List, Optional, Any, Dict
import numpy as np
from pathlib import Path

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class SiliconFlowEmbeddings(BaseModel, Embeddings):
    """
    硅基流动 Embeddings 实现（通过 LLMRouter）
    
    使用现有的 LLMRouter 基础设施调用嵌入 API，
    遵循 LangChain Embeddings 接口规范
    """
    
    model_name: str = Field(default="BAAI/bge-m3", description="嵌入模型名称")
    provider: str = Field(default="siliconflow", description="提供商")
    batch_size: int = Field(default=32, description="批处理大小")
    timeout: int = Field(default=60, description="API 超时时间（秒）")
    
    # 内部状态
    _llm_router: Any = None
    _dimension: int = 1024
    
    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        """初始化并设置 LLM Router"""
        super().__init__(**data)
        
        try:
            from app.infrastructure.llm.router import llm_router
            self._llm_router = llm_router
            
            # 推断向量维度
            self._dimension = self._infer_dimension(self.model_name)
            
            logger.info(f"初始化 SiliconFlowEmbeddings: model={self.model_name}, dim={self._dimension}")
            
        except Exception as e:
            logger.error(f"初始化 SiliconFlowEmbeddings 失败: {e}")
            raise
    
    @staticmethod
    def _infer_dimension(model_name: str) -> int:
        """根据模型名称推断向量维度"""
        dimension_map = {
            "BAAI/bge-small-zh-v1.5": 512,
            "BAAI/bge-base-zh-v1.5": 768,
            "BAAI/bge-large-zh-v1.5": 1024,
            "BAAI/bge-m3": 1024,
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }
        return dimension_map.get(model_name, 768)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量嵌入文档
        
        Args:
            texts: 文档文本列表
            
        Returns:
            List[List[float]]: 向量列表
        """
        if not texts:
            return []
        
        try:
            # 过滤空文本
            valid_texts = [text.strip() for text in texts if text and text.strip()]
            if not valid_texts:
                logger.warning("所有输入文本为空")
                return []
            
            logger.debug(f"批量嵌入 {len(valid_texts)} 个文档")
            
            # 使用批量 API
            vectors = self._call_embedding_batch(valid_texts)
            
            logger.info(f"批量嵌入完成: {len(vectors)} 个向量")
            return vectors
            
        except Exception as e:
            logger.error(f"批量嵌入失败: {e}")
            raise RuntimeError(f"批量嵌入失败: {e}")
    
    def embed_query(self, text: str) -> List[float]:
        """
        嵌入单个查询文本
        
        Args:
            text: 查询文本
            
        Returns:
            List[float]: 向量
        """
        if not text or not text.strip():
            raise ValueError("查询文本不能为空")
        
        try:
            logger.debug(f"嵌入查询: '{text[:50]}...'")
            
            # 调用单个嵌入 API
            vector = self._call_embedding_single(text.strip())
            
            return vector
            
        except Exception as e:
            logger.error(f"嵌入查询失败: {e}")
            raise RuntimeError(f"嵌入查询失败: {e}")
    
    def _call_embedding_single(self, text: str) -> List[float]:
        """
        调用单个嵌入 API
        
        Args:
            text: 输入文本
            
        Returns:
            List[float]: 向量
        """
        try:
            from app.infrastructure.llm.router.types import LLMRequest
            
            # 构建请求
            request = LLMRequest(
                provider=self.provider,
                model=self.model_name,
                messages=[],  # embedding 不使用 messages
                temperature=0.0,
                max_tokens=0,
                timeout=self.timeout
            )
            request.input_text = text
            
            # 调用 LLM router
            response = self._llm_router.generate_embedding(request)
            
            if response and hasattr(response, 'embedding') and response.embedding:
                vector = response.embedding
                
                # 验证维度
                if len(vector) != self._dimension:
                    logger.warning(f"向量维度不匹配: 期望{self._dimension}, 实际{len(vector)}")
                    self._dimension = len(vector)
                
                return vector
            else:
                raise RuntimeError("LLM router 返回的 embedding 为空")
                
        except Exception as e:
            logger.error(f"调用嵌入 API 失败: {e}")
            raise
    
    def _call_embedding_batch(self, texts: List[str]) -> List[List[float]]:
        """
        调用批量嵌入 API
        
        Args:
            texts: 输入文本列表
            
        Returns:
            List[List[float]]: 向量列表
        """
        try:
            from app.infrastructure.llm.router.types import LLMRequest
            
            # 分批处理
            all_vectors = []
            
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                
                # 构建批量请求
                request = LLMRequest(
                    provider=self.provider,
                    model=self.model_name,
                    messages=[],
                    temperature=0.0,
                    max_tokens=0,
                    timeout=self.timeout
                )
                request.input_texts = batch
                
                # 调用批量 embedding
                response = self._llm_router.generate_embedding_batch(request)
                
                if response and hasattr(response, 'embeddings') and response.embeddings:
                    vectors = response.embeddings
                    
                    # 验证维度
                    if vectors and len(vectors[0]) != self._dimension:
                        logger.warning(f"向量维度不匹配: 期望{self._dimension}, 实际{len(vectors[0])}")
                        self._dimension = len(vectors[0])
                    
                    all_vectors.extend(vectors)
                else:
                    raise RuntimeError(f"批次 {i//self.batch_size + 1} 返回的 embeddings 为空")
            
            return all_vectors
            
        except Exception as e:
            logger.error(f"调用批量嵌入 API 失败: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        """获取向量维度"""
        return self._dimension


def create_cached_embeddings(
    model_name: str = "BAAI/bge-m3",
    provider: str = "siliconflow",
    cache_dir: Optional[str] = None,
    namespace: Optional[str] = None,
) -> Embeddings:
    """
    创建带缓存的 Embeddings 实例
    
    Args:
        model_name: 嵌入模型名称
        provider: 提供商
        cache_dir: 缓存目录路径（None = 禁用缓存）
        namespace: 缓存命名空间（用于隔离不同模型）
        
    Returns:
        Embeddings: LangChain Embeddings 实例（可能带缓存）
    """
    # 创建基础 embeddings
    base_embeddings = SiliconFlowEmbeddings(
        model_name=model_name,
        provider=provider
    )
    
    # 如果不需要缓存，直接返回
    if cache_dir is None:
        logger.info(f"创建 Embeddings（无缓存）: model={model_name}")
        return base_embeddings
    
    # 启用缓存
    try:
        from langchain.storage import LocalFileStore
        from langchain_community.embeddings import CacheBackedEmbeddings
        
        # 创建缓存存储
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        
        store = LocalFileStore(str(cache_path))
        
        # 使用模型名作为默认命名空间
        if namespace is None:
            namespace = model_name.replace("/", "_")
        
        # 创建带缓存的 embeddings
        cached_embeddings = CacheBackedEmbeddings.from_bytes_store(
            underlying_embeddings=base_embeddings,
            document_embedder_store=store,
            namespace=namespace,
        )
        
        logger.info(f"创建 CachedEmbeddings: model={model_name}, cache={cache_dir}, namespace={namespace}")
        return cached_embeddings
        
    except ImportError as e:
        logger.warning(f"无法导入缓存模块，降级到无缓存模式: {e}")
        return base_embeddings
    except Exception as e:
        logger.error(f"创建缓存失败，降级到无缓存模式: {e}")
        return base_embeddings


def embeddings_to_numpy(vectors: List[List[float]]) -> np.ndarray:
    """
    将 LangChain embeddings 转换为 NumPy 数组
    
    Args:
        vectors: 向量列表
        
    Returns:
        np.ndarray: NumPy 数组
    """
    return np.array(vectors, dtype=np.float32)


def numpy_to_embeddings(vectors: np.ndarray) -> List[List[float]]:
    """
    将 NumPy 数组转换为 LangChain embeddings 格式
    
    Args:
        vectors: NumPy 数组
        
    Returns:
        List[List[float]]: 向量列表
    """
    return vectors.tolist()







