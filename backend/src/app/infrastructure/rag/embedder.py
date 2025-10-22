#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedder - 向量化器

使用API调用获取文本向量表示
支持硅基流动等提供商的embedding模型，不依赖本地模型
"""

import logging
from typing import List, Union, Optional, Dict, Any
import numpy as np
from dataclasses import dataclass
from functools import lru_cache
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """嵌入结果数据类"""
    text: str
    vector: np.ndarray
    model_name: str
    dimension: int


class Embedder:
    """文本嵌入器 - 基于API调用，带LRU缓存优化"""
    
    def __init__(self, model_name: str = "BAAI/bge-m3", provider: str = "siliconflow", batch_size: int = 32, cache_size: int = 10000):
        """
        初始化嵌入器
        
        Args:
            model_name: embedding模型名称（默认BAAI/bge-m3，SiliconFlow支持）
            provider: 模型提供商 ("siliconflow", "openai", "deepseek")
            batch_size: 批处理大小
            cache_size: LRU缓存大小（默认10000）
        """
        self.model_name = model_name
        self.provider = provider
        self.batch_size = batch_size
        self.cache_size = cache_size
        self.logger = logging.getLogger(__name__)
        
        # 获取LLM客户端来调用embedding API
        self._llm_service = self._get_llm_service()
        
        # 根据模型推断维度（实际项目中可通过API调用获取）
        self._dimension = self._infer_model_dimension()
        
        # LRU缓存 - 避免重复计算相同文本
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        self.logger.info(f"初始化Embedding API调用: provider={provider}, model={model_name}, dim={self._dimension}, cache={cache_size}")
    
    def _get_llm_service(self):
        """获取LLM服务实例"""
        try:
            from app.services.llm_service import LLMService
            return LLMService()
        except Exception as e:
            self.logger.error(f"获取LLM服务失败: {e}")
            raise
    
    def _infer_model_dimension(self) -> int:
        """根据模型名称推断向量维度"""
        # 常见embedding模型的维度映射
        dimension_map = {
            "BAAI/bge-small-zh-v1.5": 512,
            "BAAI/bge-base-zh-v1.5": 768,
            "BAAI/bge-large-zh-v1.5": 1024,
            "BAAI/bge-m3": 1024,
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }
        
        return dimension_map.get(self.model_name, 768)  # 默认768维
    
    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        # 使用模型名+文本内容的hash作为缓存键
        content = f"{self.model_name}:{text.strip()}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_from_cache(self, text: str) -> Optional[np.ndarray]:
        """从缓存获取向量"""
        cache_key = self._get_cache_key(text)
        if cache_key in self._embedding_cache:
            self._cache_hits += 1
            return self._embedding_cache[cache_key]
        self._cache_misses += 1
        return None
    
    def _put_to_cache(self, text: str, vector: np.ndarray):
        """将向量放入缓存"""
        cache_key = self._get_cache_key(text)
        # LRU策略：如果缓存满了，删除最旧的条目
        if len(self._embedding_cache) >= self.cache_size:
            # 删除第一个条目（最旧的）
            first_key = next(iter(self._embedding_cache))
            del self._embedding_cache[first_key]
        self._embedding_cache[cache_key] = vector
    
    def embed_single(self, text: str) -> EmbeddingResult:
        """
        对单个文本进行嵌入（带缓存）
        
        Args:
            text: 输入文本
            
        Returns:
            EmbeddingResult: 嵌入结果
        """
        if not text.strip():
            raise ValueError("输入文本不能为空")
        
        # 先检查缓存
        cached_vector = self._get_from_cache(text)
        if cached_vector is not None:
            return EmbeddingResult(
                text=text,
                vector=cached_vector,
                model_name=self.model_name,
                dimension=len(cached_vector)
            )
        
        try:
            # 调用embedding API
            vector = self._call_embedding_api(text)
            
            # 放入缓存
            self._put_to_cache(text, vector)
            
            return EmbeddingResult(
                text=text,
                vector=vector,
                model_name=self.model_name,
                dimension=len(vector)
            )
            
        except Exception as e:
            self.logger.error(f"embedding API调用失败: {e}")
            raise
    
    def embed_batch(self, texts: List[str], show_progress: bool = True) -> List[EmbeddingResult]:
        """
        批量嵌入文本（真正的批量API调用+缓存优化）
        
        Args:
            texts: 文本列表
            show_progress: 是否显示进度
            
        Returns:
            List[EmbeddingResult]: 嵌入结果列表
        """
        if not texts:
            return []
        
        # 过滤空文本
        valid_texts = [text for text in texts if text.strip()]
        if len(valid_texts) != len(texts):
            self.logger.warning(f"过滤了 {len(texts) - len(valid_texts)} 个空文本")
        
        if not valid_texts:
            return []
        
        # 分离已缓存和未缓存的文本
        cached_results = {}
        texts_to_compute = []
        text_indices = {}  # 记录原始位置
        
        for idx, text in enumerate(valid_texts):
            cached_vector = self._get_from_cache(text)
            if cached_vector is not None:
                cached_results[idx] = EmbeddingResult(
                    text=text,
                    vector=cached_vector,
                    model_name=self.model_name,
                    dimension=len(cached_vector)
                )
            else:
                text_indices[len(texts_to_compute)] = idx
                texts_to_compute.append(text)
        
        cache_hit_rate = len(cached_results) / len(valid_texts) * 100 if valid_texts else 0
        self.logger.info(f"批量嵌入 {len(valid_texts)} 个文本: {len(cached_results)} 个来自缓存({cache_hit_rate:.1f}%), {len(texts_to_compute)} 个需要计算")
        
        # 如果全部命中缓存，直接返回
        if not texts_to_compute:
            return [cached_results[i] for i in range(len(valid_texts))]
        
        # 分批处理API调用（使用真正的批量API）
        computed_results = {}
        for i in range(0, len(texts_to_compute), self.batch_size):
            batch = texts_to_compute[i:i + self.batch_size]
            
            try:
                # 调用批量embedding API
                vectors = self._call_embedding_api_batch(batch)
                
                # 构建结果并放入缓存
                for j, (text, vector) in enumerate(zip(batch, vectors)):
                    original_idx = text_indices[i + j]
                    computed_results[original_idx] = EmbeddingResult(
                        text=text,
                        vector=vector,
                        model_name=self.model_name,
                        dimension=len(vector)
                    )
                    # 放入缓存
                    self._put_to_cache(text, vector)
                    
            except Exception as e:
                self.logger.error(f"批量嵌入失败 (batch {i//self.batch_size + 1}): {e}")
                # 继续处理其他批次
                continue
        
        # 合并缓存结果和计算结果，按原始顺序
        final_results = []
        for i in range(len(valid_texts)):
            if i in cached_results:
                final_results.append(cached_results[i])
            elif i in computed_results:
                final_results.append(computed_results[i])
        
        self.logger.info(f"批量嵌入完成: {len(final_results)} 个结果")
        return final_results
    
    def _call_embedding_api_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        批量调用embedding API获取向量
        
        Args:
            texts: 输入文本列表
            
        Returns:
            List[np.ndarray]: 向量数组列表
        """
        try:
            if self.provider == "siliconflow":
                return self._call_siliconflow_embedding_batch(texts)
            else:
                # 其他provider降级到逐个调用
                self.logger.warning(f"Provider '{self.provider}' 不支持批量embedding，降级到逐个调用")
                return [self._call_embedding_api(text) for text in texts]
                
        except Exception as e:
            self.logger.error(f"批量embedding API调用失败: {e}")
            raise RuntimeError(f"批量Embedding API调用失败: {e}")
    
    def _call_embedding_api(self, text: str) -> np.ndarray:
        """
        调用embedding API获取向量
        
        Args:
            text: 输入文本
            
        Returns:
            np.ndarray: 向量数组
        """
        try:
            # 构造embedding请求
            # 注意：这里使用了一个简化的方案，实际需要根据具体的API格式调整
            # 目前大多数embedding API都是通过HTTP POST调用
            
            if self.provider == "openai":
                return self._call_openai_embedding(text)
            elif self.provider == "siliconflow":
                return self._call_siliconflow_embedding(text)
            elif self.provider == "deepseek":
                return self._call_deepseek_embedding(text)
            else:
                # 默认尝试通过现有LLM基础设施调用
                return self._call_generic_embedding(text)
                
        except Exception as e:
            self.logger.error(f"embedding API调用失败: {e}")
            # 严格按照指南要求：不做兜底，直接抛出异常
            raise RuntimeError(f"Embedding API调用失败，不提供降级处理: {e}")
    
    def _call_generic_embedding(self, text: str) -> np.ndarray:
        """通用embedding API调用"""
        # 严格按照指南要求：不支持的provider直接抛出异常
        raise NotImplementedError(f"Embedding provider '{self.provider}' 未实现，不提供降级处理")
    
    def _call_openai_embedding(self, text: str) -> np.ndarray:
        """OpenAI embedding API调用"""
        # 严格按照指南要求：未实现的API直接抛出异常
        raise NotImplementedError("OpenAI embedding API调用未实现，不提供降级处理")
    
    def _call_siliconflow_embedding_batch(self, texts: List[str]) -> List[np.ndarray]:
        """硅基流动批量embedding API调用"""
        try:
            # 验证输入
            if not texts or not isinstance(texts, list):
                raise ValueError(f"input_texts必须是列表，实际类型: {type(texts)}")
            
            # 确保所有元素都是字符串
            validated_texts = []
            for i, text in enumerate(texts):
                if not isinstance(text, str):
                    raise ValueError(f"input_texts[{i}]必须是字符串，实际类型: {type(text)}")
                if not text.strip():
                    raise ValueError(f"input_texts[{i}]不能为空")
                validated_texts.append(str(text).strip())
            
            # 直接使用LLM router的embedding功能
            from ...infrastructure.llm.router import llm_router
            from ...infrastructure.llm.router.types import LLMRequest
            
            # 构建批量embedding请求
            request = LLMRequest(
                provider="siliconflow",
                model=self.model_name,
                messages=[],  # embedding不使用messages
                temperature=0.0,
                max_tokens=0,
                timeout=60  # 批量请求可能需要更长时间
            )
            
            # 添加embedding特有字段（批量）
            request.input_texts = validated_texts
            
            # 调用LLM router的批量embedding方法
            response = llm_router.generate_embedding_batch(request)
            
            if response and hasattr(response, 'embeddings') and response.embeddings:
                vectors = []
                for embedding in response.embeddings:
                    vector = np.array(embedding, dtype=np.float32)
                    
                    # 检查维度
                    if vector.shape[0] != self._dimension:
                        self.logger.warning(f"向量维度不匹配: 期望{self._dimension}, 实际{vector.shape[0]}")
                        # 更新维度以匹配实际返回
                        self._dimension = vector.shape[0]
                    
                    vectors.append(vector)
                
                return vectors
            else:
                raise Exception("LLM router返回的批量embedding为空")
                
        except Exception as e:
            self.logger.error(f"SiliconFlow批量embedding API调用失败: {e}")
            # 严格按照指南要求：不做兜底，直接抛出异常
            raise RuntimeError(f"SiliconFlow批量embedding API调用失败: {e}")
    
    def _call_siliconflow_embedding(self, text: str) -> np.ndarray:
        """硅基流动 embedding API调用（IMPROOVE_GUIDE.md第5.4节要求）"""
        try:
            # 验证输入
            if not isinstance(text, str):
                raise ValueError(f"input_text必须是字符串，实际类型: {type(text)}")
            if not text or not text.strip():
                raise ValueError("input_text不能为空")
            
            # 直接使用LLM router的embedding功能
            from ...infrastructure.llm.router import llm_router
            from ...infrastructure.llm.router.types import LLMRequest
            
            # 构建embedding请求
            request = LLMRequest(
                provider="siliconflow",
                model=self.model_name,
                messages=[],  # embedding不使用messages
                temperature=0.0,
                max_tokens=0,
                timeout=30
            )
            
            # 添加embedding特有字段（确保是字符串）
            request.input_text = str(text).strip()
            
            # 调用LLM router的embedding方法
            response = llm_router.generate_embedding(request)
            
            if response and hasattr(response, 'embedding') and response.embedding:
                vector = np.array(response.embedding, dtype=np.float32)
                
                # 检查维度
                if vector.shape[0] != self._dimension:
                    self.logger.warning(f"向量维度不匹配: 期望{self._dimension}, 实际{vector.shape[0]}")
                    # 更新维度以匹配实际返回
                    self._dimension = vector.shape[0]
                
                return vector
            else:
                raise Exception("LLM router返回的embedding为空")
                
        except Exception as e:
            self.logger.error(f"SiliconFlow embedding API调用失败: {e}")
            # 严格按照指南要求：不做兜底，直接抛出异常
            raise RuntimeError(f"SiliconFlow embedding API调用失败: {e}")
    
    def _call_deepseek_embedding(self, text: str) -> np.ndarray:
        """DeepSeek embedding API调用"""
        # 严格按照指南要求：未实现的API直接抛出异常
        raise NotImplementedError("DeepSeek embedding API调用未实现，不提供降级处理")
    
    def embed_documents(self, documents: List[Dict[str, Any]], text_field: str = "text") -> List[Dict[str, Any]]:
        """
        为文档列表添加嵌入向量
        
        Args:
            documents: 文档列表，每个文档是一个字典
            text_field: 文本字段名
            
        Returns:
            List[Dict[str, Any]]: 添加了嵌入向量的文档列表
        """
        if not documents:
            return []
        
        # 提取文本
        texts = []
        for doc in documents:
            if text_field not in doc:
                raise ValueError(f"文档中缺少文本字段: {text_field}")
            texts.append(doc[text_field])
        
        # 批量嵌入
        embedding_results = self.embed_batch(texts)
        
        # 添加向量到文档
        enhanced_documents = []
        for doc, embedding in zip(documents, embedding_results):
            enhanced_doc = dict(doc)
            enhanced_doc.update({
                "vector": embedding.vector.tolist(),  # 转换为列表以便JSON序列化
                "embedding_model": self.model_name,
                "vector_dimension": embedding.dimension,
            })
            enhanced_documents.append(enhanced_doc)
        
        return enhanced_documents
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            float: 余弦相似度 (0-1)
        """
        embedding1 = self.embed_single(text1)
        embedding2 = self.embed_single(text2)
        
        # 计算余弦相似度
        similarity = np.dot(embedding1.vector, embedding2.vector)
        return float(similarity)
    
    def find_most_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[tuple]:
        """
        找到最相似的候选文本
        
        Args:
            query: 查询文本
            candidates: 候选文本列表
            top_k: 返回的结果数量
            
        Returns:
            List[tuple]: (文本, 相似度分数) 的列表，按相似度降序排列
        """
        if not candidates:
            return []
        
        # 嵌入查询和候选文本
        query_embedding = self.embed_single(query)
        candidate_embeddings = self.embed_batch(candidates, show_progress=False)
        
        # 计算相似度
        similarities = []
        for candidate, embedding in zip(candidates, candidate_embeddings):
            similarity = np.dot(query_embedding.vector, embedding.vector)
            similarities.append((candidate, float(similarity)))
        
        # 按相似度排序并返回top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    @property
    def dimension(self) -> int:
        """获取向量维度"""
        return self._dimension
    
    @property
    def is_loaded(self) -> bool:
        """检查模型是否已加载（API模式下总是可用）"""
        return self._llm_service is not None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache_size": len(self._embedding_cache),
            "cache_capacity": self.cache_size,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._embedding_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self.logger.info("Embedding缓存已清空")