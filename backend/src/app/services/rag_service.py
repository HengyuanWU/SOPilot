#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Service - RAG系统服务层

为应用的其他部分提供RAG功能的统一接口
"""

import logging
from typing import List, Dict, Any, Optional
from functools import lru_cache

from ..core.settings import get_settings
from ..infrastructure.rag import RAGPipeline, RAGConfig
from ..infrastructure.rag.prompt_builder import PromptContext

logger = logging.getLogger(__name__)


class RAGService:
    """RAG服务类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._pipeline: Optional[RAGPipeline] = None
    
    @property
    def pipeline(self) -> RAGPipeline:
        """获取RAG管线实例（延迟初始化）"""
        if self._pipeline is None:
            self._pipeline = create_rag_pipeline()
        return self._pipeline
    
    def is_available(self) -> bool:
        """检查RAG系统是否可用"""
        try:
            status = self.pipeline.get_pipeline_status()
            return (
                status.get("components", {}).get("qdrant_health", False) and
                status.get("components", {}).get("embedder_loaded", False)
            )
        except Exception as e:
            self.logger.error(f"RAG可用性检查失败: {e}")
            return False
    
    def enhance_prompt(self, base_prompt: str, query: str, top_k: int = 4, 
                      include_kg: bool = True) -> PromptContext:
        """
        增强提示词
        
        Args:
            base_prompt: 基础提示词
            query: 检索查询
            top_k: 检索结果数量
            include_kg: 是否包含知识图谱检索
            
        Returns:
            PromptContext: 增强后的提示上下文
        """
        try:
            if not self.is_available():
                self.logger.warning("RAG系统不可用，返回原始提示")
                return PromptContext(
                    enhanced_prompt=base_prompt,
                    evidence_count=0,
                    sources=[],
                    citations=[],
                    context_length=len(base_prompt)
                )
            
            return self.pipeline.build_enhanced_prompt(
                base_prompt=base_prompt,
                query=query,
                top_k=top_k,
                include_kg=include_kg
            )
            
        except Exception as e:
            self.logger.error(f"提示增强失败: {e}")
            # 返回原始提示作为后备
            return PromptContext(
                enhanced_prompt=base_prompt,
                evidence_count=0,
                sources=[],
                citations=[],
                context_length=len(base_prompt)
            )
    
    def retrieve_evidence(self, query: str, top_k: int = 4, 
                         include_kg: bool = True, scope: str = None) -> Dict[str, Any]:
        """
        检索相关证据
        
        Args:
            query: 检索查询
            top_k: 检索结果数量
            include_kg: 是否包含知识图谱检索
            scope: 检索范围
            
        Returns:
            Dict[str, Any]: 检索结果
        """
        try:
            if not self.is_available():
                self.logger.warning("RAG系统不可用，返回空结果")
                return {
                    "query": query,
                    "evidence": [],
                    "sources": [],
                    "metadata": {"error": "RAG系统不可用"}
                }
            
            result = self.pipeline.retrieve(
                query=query,
                top_k=top_k,
                include_kg=include_kg,
                scope=scope
            )
            
            return {
                "query": query,
                "evidence": [
                    {
                        "id": e.id,
                        "type": e.type,
                        "content": e.content,
                        "score": e.score,
                        "sources": e.sources,
                    }
                    for e in result.merged_evidence
                ],
                "sources": list(set(source for e in result.merged_evidence for source in e.sources)),
                "metadata": result.metadata
            }
            
        except Exception as e:
            self.logger.error(f"证据检索失败: {e}")
            return {
                "query": query,
                "evidence": [],
                "sources": [],
                "metadata": {"error": str(e)}
            }
    
    def search_similar_content(self, content: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        搜索相似内容
        
        Args:
            content: 内容文本
            top_k: 返回结果数量
            
        Returns:
            List[Dict[str, Any]]: 相似内容列表
        """
        try:
            if not self.is_available():
                return []
            
            # 使用向量检索找相似内容
            vector_results = self.pipeline.vector_retriever.search(
                query=content[:200],  # 使用内容的前200字符作为查询
                top_k=top_k
            )
            
            return [
                {
                    "chunk_id": r.chunk_id,
                    "doc_id": r.doc_id,
                    "content": r.text,
                    "similarity": r.score,
                    "meta": r.meta,
                }
                for r in vector_results
            ]
            
        except Exception as e:
            self.logger.error(f"相似内容搜索失败: {e}")
            return []
    
    def get_context_for_topic(self, topic: str, max_length: int = 1000) -> str:
        """
        为特定主题获取上下文
        
        Args:
            topic: 主题
            max_length: 最大上下文长度
            
        Returns:
            str: 上下文文本
        """
        try:
            if not self.is_available():
                return ""
            
            # 检索相关证据
            result = self.pipeline.retrieve(
                query=topic,
                top_k=3,
                include_kg=True
            )
            
            if result.merged_evidence:
                return self.pipeline.prompt_builder.build_simple_context(
                    evidence=result.merged_evidence,
                    max_length=max_length
                )
            
            return ""
            
        except Exception as e:
            self.logger.error(f"获取主题上下文失败: {e}")
            return ""
    
    def validate_content_with_evidence(self, content: str, min_evidence_count: int = 2) -> Dict[str, Any]:
        """
        使用证据验证内容
        
        Args:
            content: 要验证的内容
            min_evidence_count: 最小证据数量
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        try:
            if not self.is_available():
                return {
                    "supported": False,
                    "evidence_count": 0,
                    "confidence": 0.0,
                    "message": "RAG系统不可用"
                }
            
            # 提取内容中的关键断言（简化版本）
            key_phrases = self._extract_key_phrases(content)
            
            total_evidence_count = 0
            all_scores = []
            
            for phrase in key_phrases:
                evidence = self.retrieve_evidence(
                    query=phrase,
                    top_k=3,
                    include_kg=True
                )
                
                evidence_count = len(evidence.get("evidence", []))
                scores = [e.get("score", 0) for e in evidence.get("evidence", [])]
                
                total_evidence_count += evidence_count
                all_scores.extend(scores)
            
            avg_confidence = sum(all_scores) / len(all_scores) if all_scores else 0.0
            supported = total_evidence_count >= min_evidence_count
            
            return {
                "supported": supported,
                "evidence_count": total_evidence_count,
                "confidence": avg_confidence,
                "message": f"找到 {total_evidence_count} 条支持证据" if supported else "支持证据不足"
            }
            
        except Exception as e:
            self.logger.error(f"内容验证失败: {e}")
            return {
                "supported": False,
                "evidence_count": 0,
                "confidence": 0.0,
                "message": f"验证过程出错: {str(e)}"
            }
    
    def _extract_key_phrases(self, content: str) -> List[str]:
        """提取内容中的关键短语（简化版本）"""
        # 简化的关键短语提取：按句子分割，取较短的句子
        sentences = content.replace('。', '.').replace('！', '!').replace('？', '?').split('.')
        
        key_phrases = []
        for sentence in sentences:
            sentence = sentence.strip()
            if 10 <= len(sentence) <= 100:  # 长度在10-100字符之间的句子
                key_phrases.append(sentence)
        
        return key_phrases[:5]  # 最多返回5个关键短语


@lru_cache()
def create_rag_pipeline() -> RAGPipeline:
    """创建RAG管线实例（缓存）"""
    settings = get_settings()
    
    config = RAGConfig(
        base_dir=settings.rag.base_dir,
        chunk_size=settings.rag.chunk_size,
        chunk_overlap=settings.rag.chunk_overlap,
        embed_model=settings.rag.embed_model,
        embed_provider=settings.rag.embed_provider,
        qdrant_url=settings.qdrant.url,
        qdrant_collection=settings.qdrant.collection,
        qdrant_distance=settings.qdrant.distance,
        vector_top_k=settings.rag.vector_top_k,
        kg_top_k=settings.rag.kg_top_k,
        final_top_k=settings.rag.top_k,
        alpha=settings.rag.alpha,
        beta=settings.rag.beta,
        use_reranker=settings.rag.use_reranker,
        kg_hop=settings.rag.hop,
        kg_rel_types=settings.rag.rel_types or [],
    )
    
    logger.info("创建RAG管线实例")
    return RAGPipeline(config)


# 全局RAG服务实例
rag_service = RAGService()