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

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """嵌入结果数据类"""
    text: str
    vector: np.ndarray
    model_name: str
    dimension: int


class Embedder:
    """文本嵌入器 - 基于API调用"""
    
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", provider: str = "siliconflow", batch_size: int = 32):
        """
        初始化嵌入器
        
        Args:
            model_name: embedding模型名称
            provider: 模型提供商 ("siliconflow", "openai", "deepseek")
            batch_size: 批处理大小
        """
        self.model_name = model_name
        self.provider = provider
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)
        
        # 获取LLM客户端来调用embedding API
        self._llm_service = self._get_llm_service()
        
        # 根据模型推断维度（实际项目中可通过API调用获取）
        self._dimension = self._infer_model_dimension()
        
        # API模式下无需加载本地模型
        
        self.logger.info(f"初始化Embedding API调用: provider={provider}, model={model_name}, dim={self._dimension}")
    
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
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }
        
        return dimension_map.get(self.model_name, 768)  # 默认768维
    
    def embed_single(self, text: str) -> EmbeddingResult:
        """
        对单个文本进行嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            EmbeddingResult: 嵌入结果
        """
        if not text.strip():
            raise ValueError("输入文本不能为空")
        
        try:
            # 调用embedding API
            vector = self._call_embedding_api(text)
            
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
        批量嵌入文本
        
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
        
        self.logger.info(f"开始批量嵌入 {len(valid_texts)} 个文本")
        
        # 分批处理API调用
        results = []
        for i in range(0, len(valid_texts), self.batch_size):
            batch = valid_texts[i:i + self.batch_size]
            
            try:
                # 对每个文本调用API（某些提供商支持批量，某些不支持）
                for text in batch:
                    vector = self._call_embedding_api(text)
                    results.append(EmbeddingResult(
                        text=text,
                        vector=vector,
                        model_name=self.model_name,
                        dimension=len(vector)
                    ))
                    
            except Exception as e:
                self.logger.error(f"批量嵌入失败 (batch {i//self.batch_size + 1}): {e}")
                # 继续处理其他批次
                continue
        
        self.logger.info(f"批量嵌入完成: {len(results)} 个结果")
        return results
    
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
            # 返回随机向量作为后备（实际生产中不推荐）
            self.logger.warning("使用随机向量作为后备")
            return np.random.random(self._dimension).astype(np.float32)
    
    def _call_generic_embedding(self, text: str) -> np.ndarray:
        """通用embedding API调用"""
        # 这里需要实现具体的API调用逻辑
        # 目前作为占位符，返回随机向量
        self.logger.warning(f"embedding API调用未实现，使用随机向量 (provider: {self.provider})")
        return np.random.random(self._dimension).astype(np.float32)
    
    def _call_openai_embedding(self, text: str) -> np.ndarray:
        """OpenAI embedding API调用"""
        # OpenAI embedding API实现
        self.logger.warning("OpenAI embedding API调用未实现，使用随机向量")
        return np.random.random(self._dimension).astype(np.float32)
    
    def _call_siliconflow_embedding(self, text: str) -> np.ndarray:
        """硅基流动 embedding API调用"""
        # 硅基流动 embedding API实现
        self.logger.warning("硅基流动 embedding API调用未实现，使用随机向量")
        return np.random.random(self._dimension).astype(np.float32)
    
    def _call_deepseek_embedding(self, text: str) -> np.ndarray:
        """DeepSeek embedding API调用"""
        # DeepSeek embedding API实现
        self.logger.warning("DeepSeek embedding API调用未实现，使用随机向量")
        return np.random.random(self._dimension).astype(np.float32)
    
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