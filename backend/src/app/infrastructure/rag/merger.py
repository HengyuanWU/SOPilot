#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evidence Merger - 证据合并器

将向量检索和知识图谱检索的结果进行合并、打分归一化和去重
实现双通道检索结果的智能融合
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib

from .retrievers.retriever_vector import VectorRetrievalResult
from .retrievers.retriever_kg import KGRetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class MergedEvidence:
    """合并后的证据"""
    id: str
    type: str  # "vector", "kg", "hybrid"
    content: str
    score: float
    sources: List[str]  # 来源类型列表
    meta: Dict[str, Any]
    vector_data: Optional[VectorRetrievalResult] = None
    kg_data: Optional[KGRetrievalResult] = None


class EvidenceMerger:
    """证据合并器"""
    
    def __init__(self, alpha: float = 0.7, beta: float = 0.3):
        """
        初始化合并器
        
        Args:
            alpha: 向量检索权重
            beta: KG检索权重
        """
        self.alpha = alpha
        self.beta = beta
        self.logger = logging.getLogger(__name__)
        
        # 权重归一化
        total_weight = alpha + beta
        if total_weight > 0:
            self.alpha = alpha / total_weight
            self.beta = beta / total_weight
    
    def merge(self, vector_results: List[VectorRetrievalResult], 
              kg_results: List[KGRetrievalResult], 
              max_results: int = 10) -> List[MergedEvidence]:
        """
        合并向量检索和KG检索结果
        
        Args:
            vector_results: 向量检索结果
            kg_results: KG检索结果
            max_results: 最大返回结果数
            
        Returns:
            List[MergedEvidence]: 合并后的证据列表
        """
        try:
            self.logger.debug(f"开始合并证据: vector={len(vector_results)}, kg={len(kg_results)}")
            
            # 1. 分数归一化
            normalized_vector = self._normalize_vector_scores(vector_results)
            normalized_kg = self._normalize_kg_scores(kg_results)
            
            # 2. 转换为统一格式
            vector_evidence = self._convert_vector_to_evidence(normalized_vector)
            kg_evidence = self._convert_kg_to_evidence(normalized_kg)
            
            # 3. 合并和去重
            all_evidence = vector_evidence + kg_evidence
            merged_evidence = self._merge_and_deduplicate(all_evidence)
            
            # 4. 重新计算综合分数
            final_evidence = self._calculate_final_scores(merged_evidence)
            
            # 5. 排序并限制结果数量
            final_evidence.sort(key=lambda x: x.score, reverse=True)
            results = final_evidence[:max_results]
            
            self.logger.info(f"证据合并完成: 输入({len(vector_results)}+{len(kg_results)}) -> 输出({len(results)})")
            return results
            
        except Exception as e:
            self.logger.error(f"证据合并失败: {e}")
            return []
    
    def _normalize_vector_scores(self, results: List[VectorRetrievalResult]) -> List[VectorRetrievalResult]:
        """归一化向量检索分数"""
        if not results:
            return []
        
        # 向量检索分数通常在[0,1]范围内，已经比较标准化
        # 这里做简单的min-max归一化
        scores = [r.score for r in results]
        if not scores:
            return results
        
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score
        
        if score_range == 0:
            # 所有分数相同
            return results
        
        normalized_results = []
        for result in results:
            normalized_score = (result.score - min_score) / score_range
            # 创建新的结果对象，只更改分数
            normalized_result = VectorRetrievalResult(
                chunk_id=result.chunk_id,
                doc_id=result.doc_id,
                text=result.text,
                score=normalized_score,
                meta=result.meta
            )
            normalized_results.append(normalized_result)
        
        return normalized_results
    
    def _normalize_kg_scores(self, results: List[KGRetrievalResult]) -> List[KGRetrievalResult]:
        """归一化KG检索分数"""
        if not results:
            return []
        
        # KG分数可能需要更复杂的归一化
        scores = [r.score for r in results]
        if not scores:
            return results
        
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score
        
        if score_range == 0:
            return results
        
        normalized_results = []
        for result in results:
            # 应用路径长度和置信度的加权
            path_score = self._calculate_kg_path_score(result)
            normalized_score = (path_score - min_score) / score_range if score_range > 0 else 0.5
            
            # 创建新的结果对象
            normalized_result = KGRetrievalResult(
                type=result.type,
                score=normalized_score,
                content=result.content,
                data=result.data,
                explanation=result.explanation
            )
            normalized_results.append(normalized_result)
        
        return normalized_results
    
    def _calculate_kg_path_score(self, kg_result: KGRetrievalResult) -> float:
        """计算KG路径分数"""
        base_score = kg_result.score
        
        # 根据类型调整分数
        if kg_result.type == "entity":
            # 实体结果直接使用原分数
            return base_score
        elif kg_result.type == "path":
            # 路径结果考虑路径长度
            path_length = kg_result.data.get("path_length", 1)
            length_penalty = 1.0 / (path_length + 1)
            return base_score * length_penalty
        elif kg_result.type == "subgraph":
            # 子图结果考虑节点数和关系复杂度
            nodes = kg_result.data.get("nodes", [])
            relationships = kg_result.data.get("relationships", [])
            
            # 节点数奖励（但不能太多）
            node_bonus = min(len(nodes) * 0.1, 0.3)
            
            # 关系置信度平均值
            rel_confidences = [rel.get("confidence", 0.8) for rel in relationships]
            avg_confidence = sum(rel_confidences) / len(rel_confidences) if rel_confidences else 0.8
            
            return base_score * (1 + node_bonus) * avg_confidence
        
        return base_score
    
    def _convert_vector_to_evidence(self, vector_results: List[VectorRetrievalResult]) -> List[MergedEvidence]:
        """将向量检索结果转换为证据格式"""
        evidence_list = []
        
        for result in vector_results:
            evidence_id = self._generate_evidence_id("vector", result.chunk_id)
            
            evidence = MergedEvidence(
                id=evidence_id,
                type="vector",
                content=result.text,
                score=result.score * self.alpha,  # 应用权重
                sources=["vector"],
                meta={
                    "chunk_id": result.chunk_id,
                    "doc_id": result.doc_id,
                    "vector_score": result.score,
                    **result.meta
                },
                vector_data=result
            )
            evidence_list.append(evidence)
        
        return evidence_list
    
    def _convert_kg_to_evidence(self, kg_results: List[KGRetrievalResult]) -> List[MergedEvidence]:
        """将KG检索结果转换为证据格式"""
        evidence_list = []
        
        for result in kg_results:
            evidence_id = self._generate_evidence_id("kg", str(result.data))
            
            evidence = MergedEvidence(
                id=evidence_id,
                type="kg",
                content=result.content,
                score=result.score * self.beta,  # 应用权重
                sources=["kg"],
                meta={
                    "kg_type": result.type,
                    "kg_score": result.score,
                    "explanation": result.explanation,
                    **result.data
                },
                kg_data=result
            )
            evidence_list.append(evidence)
        
        return evidence_list
    
    def _merge_and_deduplicate(self, evidence_list: List[MergedEvidence]) -> List[MergedEvidence]:
        """合并和去重证据"""
        # 简单的去重策略：基于内容相似度
        merged_map = {}
        
        for evidence in evidence_list:
            # 生成内容哈希作为去重键
            content_hash = self._get_content_hash(evidence.content)
            
            if content_hash in merged_map:
                # 已存在相似内容，合并
                existing = merged_map[content_hash]
                merged = self._merge_similar_evidence(existing, evidence)
                merged_map[content_hash] = merged
            else:
                # 新内容
                merged_map[content_hash] = evidence
        
        return list(merged_map.values())
    
    def _merge_similar_evidence(self, evidence1: MergedEvidence, evidence2: MergedEvidence) -> MergedEvidence:
        """合并相似的证据"""
        # 选择分数更高的作为主要证据
        if evidence1.score >= evidence2.score:
            primary, secondary = evidence1, evidence2
        else:
            primary, secondary = evidence2, evidence1
        
        # 合并来源
        combined_sources = list(set(primary.sources + secondary.sources))
        
        # 综合分数（加权平均）
        combined_score = (primary.score + secondary.score * 0.5) / 1.5
        
        # 合并元数据
        combined_meta = dict(primary.meta)
        for key, value in secondary.meta.items():
            if key not in combined_meta:
                combined_meta[f"secondary_{key}"] = value
        
        return MergedEvidence(
            id=primary.id,
            type="hybrid" if len(combined_sources) > 1 else primary.type,
            content=primary.content,  # 使用主要证据的内容
            score=combined_score,
            sources=combined_sources,
            meta=combined_meta,
            vector_data=primary.vector_data or secondary.vector_data,
            kg_data=primary.kg_data or secondary.kg_data
        )
    
    def _calculate_final_scores(self, evidence_list: List[MergedEvidence]) -> List[MergedEvidence]:
        """重新计算最终分数"""
        for evidence in evidence_list:
            # 基础分数
            base_score = evidence.score
            
            # 多源奖励
            source_bonus = 0.1 if len(evidence.sources) > 1 else 0
            
            # 内容长度适度奖励
            content_length = len(evidence.content)
            length_bonus = min(content_length / 1000, 0.1)  # 最多10%奖励
            
            # 最终分数
            evidence.score = base_score + source_bonus + length_bonus
        
        return evidence_list
    
    def _generate_evidence_id(self, prefix: str, content: str) -> str:
        """生成证据ID"""
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        return f"{prefix}_{content_hash}"
    
    def _get_content_hash(self, content: str) -> str:
        """获取内容哈希（用于去重）"""
        # 简化内容（去除标点和空格）进行哈希
        simplified = ''.join(c.lower() for c in content if c.isalnum())
        return hashlib.md5(simplified.encode('utf-8')).hexdigest()[:16]
    
    def get_merge_statistics(self, merged_evidence: List[MergedEvidence]) -> Dict[str, Any]:
        """获取合并统计信息"""
        if not merged_evidence:
            return {}
        
        # 按类型统计
        type_counts = {}
        source_counts = {}
        
        for evidence in merged_evidence:
            type_counts[evidence.type] = type_counts.get(evidence.type, 0) + 1
            for source in evidence.sources:
                source_counts[source] = source_counts.get(source, 0) + 1
        
        # 分数统计
        scores = [e.score for e in merged_evidence]
        
        return {
            "total_evidence": len(merged_evidence),
            "type_distribution": type_counts,
            "source_distribution": source_counts,
            "score_stats": {
                "min": min(scores),
                "max": max(scores),
                "avg": sum(scores) / len(scores),
            },
            "hybrid_count": sum(1 for e in merged_evidence if e.type == "hybrid"),
            "alpha": self.alpha,
            "beta": self.beta,
        }