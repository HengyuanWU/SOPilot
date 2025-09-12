#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BGE Reranker - BGE交叉编码器复排

使用BGE reranker模型对检索结果进行重新排序
可选组件，可以通过配置开启或关闭
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

from ..merger import MergedEvidence

logger = logging.getLogger(__name__)


@dataclass
class RerankedResult:
    """重排后的结果"""
    evidence: MergedEvidence
    rerank_score: float
    original_score: float


class BGEReranker:
    """BGE交叉编码器重排器"""
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-base", device: str = "auto", enabled: bool = True):
        """
        初始化重排器
        
        Args:
            model_name: BGE重排模型名称
            device: 设备类型
            enabled: 是否启用重排
        """
        self.model_name = model_name
        self.device = device
        self.enabled = enabled
        self.logger = logging.getLogger(__name__)
        
        self._model = None
        self._tokenizer = None
        
        if self.enabled:
            self._load_model()
    
    def _load_model(self):
        """初始化重排器（基于API调用，不加载本地模型）"""
        try:
            # 检查是否有可用的API服务
            self.logger.info(f"初始化BGE重排API调用: {self.model_name}")
            
            # 获取LLM服务用于API调用
            from app.services.llm_service import LLMService
            self._llm_service = LLMService()
            
            self.logger.info("BGE重排器初始化完成（API模式）")
            
        except ImportError:
            self.logger.warning("无法获取LLM服务，禁用重排功能")
            self.enabled = False
        except Exception as e:
            self.logger.error(f"BGE重排器初始化失败: {e}")
            self.enabled = False
    
    def rerank(self, query: str, evidence_list: List[MergedEvidence], top_k: Optional[int] = None) -> List[RerankedResult]:
        """
        重新排序证据
        
        Args:
            query: 查询文本
            evidence_list: 证据列表
            top_k: 返回的结果数量（如果为None，返回所有结果）
            
        Returns:
            List[RerankedResult]: 重排后的结果列表
        """
        if not self.enabled or not evidence_list:
            # 如果未启用或没有证据，返回原始排序
            return [
                RerankedResult(
                    evidence=evidence,
                    rerank_score=evidence.score,
                    original_score=evidence.score
                )
                for evidence in evidence_list
            ]
        
        try:
            self.logger.debug(f"开始BGE重排: query长度={len(query)}, 证据数={len(evidence_list)}")
            
            # 1. 准备查询-文档对
            query_doc_pairs = []
            for evidence in evidence_list:
                query_doc_pairs.append((query, evidence.content))
            
            # 2. 批量重排计分
            rerank_scores = self._compute_rerank_scores(query_doc_pairs)
            
            # 3. 创建重排结果
            reranked_results = []
            for evidence, rerank_score in zip(evidence_list, rerank_scores):
                reranked_results.append(RerankedResult(
                    evidence=evidence,
                    rerank_score=rerank_score,
                    original_score=evidence.score
                ))
            
            # 4. 按重排分数排序
            reranked_results.sort(key=lambda x: x.rerank_score, reverse=True)
            
            # 5. 限制结果数量
            if top_k is not None:
                reranked_results = reranked_results[:top_k]
            
            self.logger.info(f"BGE重排完成: 返回 {len(reranked_results)} 个结果")
            return reranked_results
            
        except Exception as e:
            self.logger.error(f"BGE重排失败: {e}")
            # 返回原始排序作为后备
            return [
                RerankedResult(
                    evidence=evidence,
                    rerank_score=evidence.score,
                    original_score=evidence.score
                )
                for evidence in evidence_list
            ]
    
    def _compute_rerank_scores(self, query_doc_pairs: List[Tuple[str, str]], batch_size: int = 8) -> List[float]:
        """
        计算重排分数（基于API调用）
        
        Args:
            query_doc_pairs: 查询-文档对列表
            batch_size: 批处理大小
            
        Returns:
            List[float]: 重排分数列表
        """
        if not self.enabled:
            # 重排器未启用，返回默认分数
            return [0.5] * len(query_doc_pairs)
        
        try:
            scores = []
            
            # 分批处理API调用
            for i in range(0, len(query_doc_pairs), batch_size):
                batch_pairs = query_doc_pairs[i:i + batch_size]
                
                # 对每对进行重排评分
                for query, doc in batch_pairs:
                    try:
                        # 调用重排API（这里简化为基于相似度的评分）
                        score = self._call_rerank_api(query, doc)
                        scores.append(score)
                    except Exception as e:
                        self.logger.warning(f"重排API调用失败: {e}")
                        # 使用文本相似度作为后备评分
                        score = self._calculate_text_similarity(query, doc)
                        scores.append(score)
            
            return scores
            
        except Exception as e:
            self.logger.error(f"计算重排分数失败: {e}")
            return [0.5] * len(query_doc_pairs)
    
    def _call_rerank_api(self, query: str, doc: str) -> float:
        """
        调用重排API（占位符实现）
        
        Args:
            query: 查询文本
            doc: 文档文本
            
        Returns:
            float: 重排分数
        """
        # TODO: 实现具体的重排API调用
        # 目前使用简单的文本相似度作为占位符
        self.logger.debug("重排API调用未实现，使用文本相似度")
        return self._calculate_text_similarity(query, doc)
    
    def _calculate_text_similarity(self, query: str, doc: str) -> float:
        """
        计算文本相似度（简单实现）
        
        Args:
            query: 查询文本
            doc: 文档文本
            
        Returns:
            float: 相似度分数
        """
        # 简单的关键词重叠计算
        query_words = set(query.lower().split())
        doc_words = set(doc.lower().split())
        
        if not query_words or not doc_words:
            return 0.0
        
        intersection = query_words.intersection(doc_words)
        union = query_words.union(doc_words)
        
        similarity = len(intersection) / len(union) if union else 0.0
        return min(max(similarity, 0.0), 1.0)  # 确保在[0,1]范围内
    
    def rerank_with_explanation(self, query: str, evidence_list: List[MergedEvidence], 
                               top_k: Optional[int] = None) -> Tuple[List[RerankedResult], Dict[str, Any]]:
        """
        重排并提供详细解释
        
        Args:
            query: 查询文本
            evidence_list: 证据列表
            top_k: 返回的结果数量
            
        Returns:
            Tuple[List[RerankedResult], Dict]: (重排结果, 解释信息)
        """
        reranked_results = self.rerank(query, evidence_list, top_k)
        
        # 生成解释信息
        explanation = {
            "enabled": self.enabled,
            "model_name": self.model_name if self.enabled else None,
            "original_count": len(evidence_list),
            "reranked_count": len(reranked_results),
            "score_changes": [],
        }
        
        # 分析分数变化
        for result in reranked_results:
            score_change = result.rerank_score - result.original_score
            explanation["score_changes"].append({
                "evidence_id": result.evidence.id,
                "original_score": result.original_score,
                "rerank_score": result.rerank_score,
                "score_change": score_change,
                "content_preview": result.evidence.content[:100] + "..." if len(result.evidence.content) > 100 else result.evidence.content,
            })
        
        return reranked_results, explanation
    
    def compare_ranking(self, query: str, evidence_list: List[MergedEvidence]) -> Dict[str, any]:
        """
        比较重排前后的排序变化
        
        Args:
            query: 查询文本
            evidence_list: 证据列表
            
        Returns:
            Dict: 比较结果
        """
        if not self.enabled:
            return {"enabled": False, "message": "重排功能未启用"}
        
        # 原始排序
        original_order = [(i, e.id, e.score) for i, e in enumerate(evidence_list)]
        
        # 重排后排序
        reranked_results = self.rerank(query, evidence_list)
        reranked_order = [(i, r.evidence.id, r.rerank_score) for i, r in enumerate(reranked_results)]
        
        # 分析排序变化
        position_changes = {}
        for new_pos, (_, evidence_id, rerank_score) in enumerate(reranked_order):
            # 找到原始位置
            original_pos = next(i for i, (_, eid, _) in enumerate(original_order) if eid == evidence_id)
            position_change = original_pos - new_pos  # 正数表示排名提升
            
            position_changes[evidence_id] = {
                "original_position": original_pos,
                "new_position": new_pos,
                "position_change": position_change,
                "rerank_score": rerank_score,
            }
        
        return {
            "enabled": True,
            "total_evidence": len(evidence_list),
            "position_changes": position_changes,
            "major_changes": [
                (eid, change) for eid, change in position_changes.items()
                if abs(change["position_change"]) >= 2
            ],
        }
    
    def get_model_info(self) -> Dict[str, any]:
        """
        获取模型信息
        
        Returns:
            Dict: 模型信息
        """
        return {
            "enabled": self.enabled,
            "model_name": self.model_name,
            "device": self.device,
            "model_loaded": self._model is not None,
            "tokenizer_loaded": self._tokenizer is not None,
        }