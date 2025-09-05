#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt Builder - 提示构造器

将检索到的证据片段和知识图谱信息转换为可读的上下文，用于增强LLM提示
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .merger import MergedEvidence

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """提示上下文"""
    enhanced_prompt: str
    evidence_count: int
    sources: List[str]
    citations: List[Dict[str, Any]]
    context_length: int


class PromptBuilder:
    """提示构造器"""
    
    def __init__(self, max_context_length: int = 4000, citation_style: str = "numbered"):
        """
        初始化提示构造器
        
        Args:
            max_context_length: 最大上下文长度
            citation_style: 引用样式 ("numbered", "bracketed", "inline")
        """
        self.max_context_length = max_context_length
        self.citation_style = citation_style
        self.logger = logging.getLogger(__name__)
    
    def build_enhanced_prompt(self, base_prompt: str, evidence: List[MergedEvidence], 
                            include_citations: bool = True) -> PromptContext:
        """
        构建增强的提示
        
        Args:
            base_prompt: 基础提示
            evidence: 检索到的证据列表
            include_citations: 是否包含引用
            
        Returns:
            PromptContext: 增强后的提示上下文
        """
        try:
            self.logger.debug(f"构建增强提示: 基础长度={len(base_prompt)}, 证据数={len(evidence)}")
            
            if not evidence:
                return PromptContext(
                    enhanced_prompt=base_prompt,
                    evidence_count=0,
                    sources=[],
                    citations=[],
                    context_length=len(base_prompt)
                )
            
            # 1. 构建证据上下文
            evidence_context = self._build_evidence_context(evidence, include_citations)
            
            # 2. 构建增强提示
            enhanced_prompt = self._combine_prompt_and_context(base_prompt, evidence_context)
            
            # 3. 处理长度限制
            final_prompt = self._truncate_if_needed(enhanced_prompt)
            
            # 4. 提取引用信息
            citations = self._extract_citations(evidence) if include_citations else []
            
            # 5. 统计信息
            sources = list(set(source for e in evidence for source in e.sources))
            
            result = PromptContext(
                enhanced_prompt=final_prompt,
                evidence_count=len(evidence),
                sources=sources,
                citations=citations,
                context_length=len(final_prompt)
            )
            
            self.logger.info(f"提示构建完成: 原长度={len(base_prompt)} -> 增强长度={len(final_prompt)}")
            return result
            
        except Exception as e:
            self.logger.error(f"提示构建失败: {e}")
            # 返回原始提示作为后备
            return PromptContext(
                enhanced_prompt=base_prompt,
                evidence_count=0,
                sources=[],
                citations=[],
                context_length=len(base_prompt)
            )
    
    def _build_evidence_context(self, evidence: List[MergedEvidence], include_citations: bool) -> str:
        """构建证据上下文"""
        context_parts = []
        
        # 按类型分组证据
        vector_evidence = [e for e in evidence if e.type == "vector"]
        kg_evidence = [e for e in evidence if e.type == "kg"]
        hybrid_evidence = [e for e in evidence if e.type == "hybrid"]
        
        # 添加上下文标题
        context_parts.append("## 参考资料\n")
        
        # 处理文档证据（向量检索）
        if vector_evidence:
            context_parts.append("### 相关文档内容：")
            for i, e in enumerate(vector_evidence, 1):
                citation = f"[{i}]" if include_citations else ""
                doc_info = self._format_document_evidence(e, citation)
                context_parts.append(doc_info)
            context_parts.append("")
        
        # 处理知识图谱证据
        if kg_evidence:
            context_parts.append("### 相关知识结构：")
            for i, e in enumerate(kg_evidence, len(vector_evidence) + 1):
                citation = f"[{i}]" if include_citations else ""
                kg_info = self._format_kg_evidence(e, citation)
                context_parts.append(kg_info)
            context_parts.append("")
        
        # 处理混合证据
        if hybrid_evidence:
            context_parts.append("### 综合信息：")
            for i, e in enumerate(hybrid_evidence, len(vector_evidence) + len(kg_evidence) + 1):
                citation = f"[{i}]" if include_citations else ""
                hybrid_info = self._format_hybrid_evidence(e, citation)
                context_parts.append(hybrid_info)
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _format_document_evidence(self, evidence: MergedEvidence, citation: str) -> str:
        """格式化文档证据"""
        content = evidence.content.strip()
        
        # 获取文档信息
        doc_id = evidence.meta.get("doc_id", "未知文档")
        chunk_id = evidence.meta.get("chunk_id", "")
        
        # 格式化输出
        if self.citation_style == "numbered":
            return f"{citation} {content}\n   来源：{doc_id}"
        elif self.citation_style == "bracketed":
            return f"[来源：{doc_id}] {content}"
        else:  # inline
            return f"{content} ({doc_id})"
    
    def _format_kg_evidence(self, evidence: MergedEvidence, citation: str) -> str:
        """格式化知识图谱证据"""
        content = evidence.content.strip()
        kg_type = evidence.meta.get("kg_type", "知识")
        explanation = evidence.meta.get("explanation", "")
        
        # 格式化输出
        formatted = f"{citation} {content}"
        
        if explanation:
            formatted += f"\n   说明：{explanation}"
        
        formatted += f"\n   类型：{kg_type}"
        
        return formatted
    
    def _format_hybrid_evidence(self, evidence: MergedEvidence, citation: str) -> str:
        """格式化混合证据"""
        content = evidence.content.strip()
        sources = ", ".join(evidence.sources)
        
        return f"{citation} {content}\n   来源：{sources}"
    
    def _combine_prompt_and_context(self, base_prompt: str, evidence_context: str) -> str:
        """合并基础提示和证据上下文"""
        # 检查基础提示是否已经包含占位符
        if "{{context}}" in base_prompt or "{context}" in base_prompt:
            # 替换占位符
            enhanced = base_prompt.replace("{{context}}", evidence_context)
            enhanced = enhanced.replace("{context}", evidence_context)
            return enhanced
        else:
            # 在提示前添加上下文
            return f"{evidence_context}\n\n{base_prompt}\n\n请基于上述参考资料回答问题。"
    
    def _truncate_if_needed(self, prompt: str) -> str:
        """如果需要，截断提示以满足长度限制"""
        if len(prompt) <= self.max_context_length:
            return prompt
        
        self.logger.warning(f"提示过长({len(prompt)} > {self.max_context_length})，进行截断")
        
        # 简单截断策略：保留前面部分和基础提示
        lines = prompt.split('\n')
        
        # 尝试找到基础提示的开始位置
        prompt_start_idx = -1
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith('#') and not line.startswith('['):
                # 可能是基础提示的开始
                remaining_length = sum(len(l) + 1 for l in lines[i:])
                if remaining_length < self.max_context_length * 0.3:  # 为基础提示保留30%空间
                    prompt_start_idx = i
                    break
        
        if prompt_start_idx > 0:
            # 保留部分上下文和完整的基础提示
            target_context_length = int(self.max_context_length * 0.7)
            context_lines = []
            current_length = 0
            
            for line in lines[:prompt_start_idx]:
                line_length = len(line) + 1
                if current_length + line_length > target_context_length:
                    break
                context_lines.append(line)
                current_length += line_length
            
            # 添加截断提示
            context_lines.append("...(内容过长，已截断)...")
            
            # 合并截断后的内容
            truncated = '\n'.join(context_lines + lines[prompt_start_idx:])
            return truncated
        else:
            # 简单截断
            return prompt[:self.max_context_length] + "...(内容过长，已截断)"
    
    def _extract_citations(self, evidence: List[MergedEvidence]) -> List[Dict[str, Any]]:
        """提取引用信息"""
        citations = []
        
        for i, e in enumerate(evidence, 1):
            citation = {
                "id": i,
                "type": e.type,
                "content_preview": e.content[:100] + "..." if len(e.content) > 100 else e.content,
                "score": e.score,
                "sources": e.sources,
            }
            
            # 添加类型特定的信息
            if e.type == "vector":
                citation.update({
                    "doc_id": e.meta.get("doc_id"),
                    "chunk_id": e.meta.get("chunk_id"),
                })
            elif e.type == "kg":
                citation.update({
                    "kg_type": e.meta.get("kg_type"),
                    "explanation": e.meta.get("explanation"),
                })
            
            citations.append(citation)
        
        return citations
    
    def build_simple_context(self, evidence: List[MergedEvidence], max_length: int = 1000) -> str:
        """
        构建简单的上下文字符串（不包含复杂格式）
        
        Args:
            evidence: 证据列表
            max_length: 最大长度
            
        Returns:
            str: 简单的上下文字符串
        """
        if not evidence:
            return ""
        
        context_parts = []
        current_length = 0
        
        for e in evidence:
            content = e.content.strip()
            content_length = len(content)
            
            if current_length + content_length > max_length:
                break
            
            context_parts.append(content)
            current_length += content_length
        
        return " ".join(context_parts)
    
    def format_for_debug(self, evidence: List[MergedEvidence]) -> Dict[str, Any]:
        """
        格式化证据用于调试显示
        
        Args:
            evidence: 证据列表
            
        Returns:
            Dict[str, Any]: 调试信息
        """
        debug_info = {
            "total_evidence": len(evidence),
            "evidence_breakdown": [],
            "sources_summary": {},
            "score_distribution": [],
        }
        
        for e in evidence:
            debug_info["evidence_breakdown"].append({
                "id": e.id,
                "type": e.type,
                "score": e.score,
                "content_length": len(e.content),
                "content_preview": e.content[:100] + "..." if len(e.content) > 100 else e.content,
                "sources": e.sources,
            })
            
            # 统计来源
            for source in e.sources:
                debug_info["sources_summary"][source] = debug_info["sources_summary"].get(source, 0) + 1
            
            # 分数分布
            debug_info["score_distribution"].append(e.score)
        
        return debug_info