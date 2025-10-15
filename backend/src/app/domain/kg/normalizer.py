#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规范化器（按IMPROOVE_GUIDE.md规范）
- 小写化、全半角、去噪
- 同义/别名映射（静态词典 + 规则）
- 术语词形归一（英文词形还原）
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["KGNormalizer"]


class KGNormalizer:
    """知识图谱实体名称规范化器。"""

    def __init__(self, settings):
        """初始化规范化器。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings
        self.min_len = settings.KG_MIN_TERM_LEN
        
        # 静态同义词映射（可扩展）
        self.synonyms = {
            "向量检索": ["向量搜索", "vector retrieval", "vector search"],
            "RAG": ["检索增强生成", "retrieval augmented generation"],
            "LLM": ["大型语言模型", "大语言模型", "large language model"],
            "embedding": ["嵌入", "向量嵌入"],
        }
        
        # 构建反向映射
        self.canonical = {}
        for canonical, aliases in self.synonyms.items():
            for alias in aliases:
                self.canonical[self._normalize_text(alias)] = canonical

    def normalize(self, draft: dict) -> dict:
        """规范化图谱数据。
        
        Args:
            draft: 原始图谱数据，包含 concepts 和 relations
            
        Returns:
            规范化后的图谱数据
        """
        # 规范化概念
        normalized_concepts = []
        seen = set()
        
        for c in draft.get("concepts", []):
            # 规范化名称
            orig_name = c["name"]
            norm_name = self._normalize_text(orig_name)
            
            # 查找同义词
            canonical_name = self.canonical.get(norm_name, norm_name)
            
            # 过滤太短的术语
            if len(canonical_name) < self.min_len:
                continue
            
            # 去重
            if canonical_name in seen:
                continue
            seen.add(canonical_name)
            
            # 更新名称和别名
            c["name"] = canonical_name
            if canonical_name != orig_name:
                aliases = c.get("aliases", [])
                if orig_name not in aliases:
                    aliases.append(orig_name)
                c["aliases"] = aliases
            
            normalized_concepts.append(c)
        
        # 规范化关系
        normalized_relations = []
        seen_rels = set()
        
        for r in draft.get("relations", []):
            # 规范化源和目标名称
            src_norm = self.canonical.get(
                self._normalize_text(r["src_name"]),
                self._normalize_text(r["src_name"])
            )
            tgt_norm = self.canonical.get(
                self._normalize_text(r["tgt_name"]),
                self._normalize_text(r["tgt_name"])
            )
            
            r["src_name"] = src_norm
            r["tgt_name"] = tgt_norm
            
            # 去重（相同的 src + relation + tgt）
            rel_key = (src_norm, r["type"], tgt_norm)
            if rel_key in seen_rels:
                continue
            seen_rels.add(rel_key)
            
            normalized_relations.append(r)
        
        return {
            "concepts": normalized_concepts,
            "relations": normalized_relations,
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        """文本规范化：小写化、全半角转换、去噪。
        
        Args:
            text: 原始文本
            
        Returns:
            规范化后的文本
        """
        # 转小写
        text = text.lower()
        
        # 全角转半角
        text = unicodedata.normalize("NFKC", text)
        
        # 移除多余空白
        text = re.sub(r"\s+", " ", text)
        
        # 去除首尾空白
        text = text.strip()
        
        return text
