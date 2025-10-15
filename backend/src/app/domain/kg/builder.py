#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NER/RE 构建器（按IMPROOVE_GUIDE.md规范）
- 粒度：以 Chunk（段落）为单位，内部再做句切分
- NER：使用 spaCy 抽取候选概念
- RE：对每个句子调用 llm_service → 受控 JSON 三元组
- 去噪：丢弃 confidence < KG_RE_MIN_CONF
"""

from __future__ import annotations

import json
import logging
from typing import Any

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

__all__ = ["KGBuilder"]

logger = logging.getLogger(__name__)

# 关系枚举
RELATION_TYPES = {
    "DEFINES", "EXPLAINS", "REQUIRES", "SIMILAR_TO", 
    "CONTRASTS_WITH", "IMPLEMENTS", "PART_OF"
}

# 中文关系映射表
RELATION_MAPPING = {
    "定义": "DEFINES",
    "解释": "EXPLAINS",
    "需要": "REQUIRES",
    "依赖": "REQUIRES",
    "相似": "SIMILAR_TO",
    "类似": "SIMILAR_TO",
    "对比": "CONTRASTS_WITH",
    "实现": "IMPLEMENTS",
    "包含": "PART_OF",
    "组成": "PART_OF",
    # 英文小写
    "defines": "DEFINES",
    "explains": "EXPLAINS",
    "requires": "REQUIRES",
    "similar to": "SIMILAR_TO",
    "contrasts with": "CONTRASTS_WITH",
    "implements": "IMPLEMENTS",
    "part of": "PART_OF",
}


class KGBuilder:
    """知识图谱构建器（NER + RE）。"""

    def __init__(self, settings):
        """初始化构建器。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings
        self.min_len = settings.KG_MIN_TERM_LEN
        self.conf_threshold = settings.KG_RE_MIN_CONF
        
        # 加载spaCy模型（仅本地NER）
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("zh_core_web_sm")
            except OSError:
                # 模型未安装，使用空分词器
                self.nlp = None
        else:
            self.nlp = None

    def extract(self, section: dict) -> dict:
        """从小节中提取概念和关系。
        
        Args:
            section: 小节数据，包含 chunks 列表
            
        Returns:
            包含 concepts 和 relations 的字典
        """
        concepts = []
        relations = []
        
        for chunk in section.get("chunks", []):
            text = chunk.get("text", "")
            chunk_id = chunk.get("id", "")
            
            # 1. NER：收集候选概念
            chunk_concepts = self._extract_concepts(text, chunk_id)
            concepts.extend(chunk_concepts)
            
            # 2. RE：提取关系（句级），传入候选概念以降低幻觉
            candidate_names = [c['name'] for c in chunk_concepts]
            chunk_relations = self._extract_relations(text, chunk_id, candidate_names)
            relations.extend(chunk_relations)
        
        # 去重
        concepts = self._dedup_concepts(concepts)
        relations = self._dedup_relations(relations)
        
        return {"concepts": concepts, "relations": relations}

    def _extract_concepts(self, text: str, chunk_id: str) -> list[dict]:
        """使用spaCy提取概念。
        
        Args:
            text: 文本内容
            chunk_id: 文本块ID
            
        Returns:
            概念列表
        """
        concepts = []
        
        if not self.nlp:
            # spaCy不可用，使用简单规则提取
            # TODO: 可以改进为基于词性标注等方法
            return concepts
        
        doc = self.nlp(text)
        
        # 收集实体
        for ent in doc.ents:
            if len(ent.text) >= self.min_len:
                concepts.append({
                    "name": ent.text,
                    "mentions": [chunk_id],
                    "type": "Concept",
                })
        
        # 收集名词短语（作为候选概念）
        # 注意：noun_chunks在中文模型中不支持，需要做兼容处理
        try:
            for chunk in doc.noun_chunks:
                if len(chunk.text) >= self.min_len:
                    concepts.append({
                        "name": chunk.text,
                        "mentions": [chunk_id],
                        "type": "Concept",
                    })
        except NotImplementedError:
            # 中文模型不支持noun_chunks，改用名词词性标注
            for token in doc:
                if token.pos_ in ("NOUN", "PROPN") and len(token.text) >= self.min_len:
                    concepts.append({
                        "name": token.text,
                        "mentions": [chunk_id],
                        "type": "Concept",
                    })
        
        return concepts

    def _extract_relations(self, text: str, chunk_id: str, candidate_concepts: list[str] = None) -> list[dict]:
        """提取关系（句级调用LLM）。
        
        Args:
            text: 文本内容
            chunk_id: 文本块ID
            candidate_concepts: 候选概念列表，用于降低LLM幻觉
            
        Returns:
            关系列表
        """
        relations = []
        
        if not self.nlp:
            # spaCy不可用，无法切分句子
            return relations
        
        doc = self.nlp(text)
        
        # 按句子处理
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            
            # 跳过过短的句子（可能是标题、列表项等）
            if len(sent_text) < 10:
                continue
            
            # 调用 llm_service 进行关系提取
            sent_relations = self._extract_relations_llm(sent_text, chunk_id, candidate_concepts)
            relations.extend(sent_relations)
        
        return relations

    def _extract_relations_llm(self, sent: str, chunk_id: str, candidates: list[str] = None) -> list[dict]:
        """使用LLM提取关系（按IMPROOVE_GUIDE.md 5.2.1节规范）。
        
        Args:
            sent: 句子文本
            chunk_id: 文本块ID
            candidates: 候选实体列表
            
        Returns:
            关系列表
        """
        # 导入llm_service（延迟导入避免循环依赖）
        from app.services.llm_service import llm_service
        
        # 截断过长句子（按指南要求，<=800汉字）
        if len(sent) > 800:
            sent = sent[:800]
        
        # 构建受控JSON Schema（按指南5.2.1节要求）
        schema = {
            'type': 'object',
            'properties': {
                'relations': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'head': {'type': 'string'},
                            'relation': {'type': 'string'},
                            'tail': {'type': 'string'},
                            'confidence': {'type': 'number'}
                        },
                        'required': ['head', 'relation', 'tail']
                    }
                }
            },
            'required': ['relations']
        }
        
        # 调用llm_service（按指南要求使用SiliconFlow + 温度0.1）
        payload = {
            'task': 're',
            'text': sent,
            'candidates': candidates or [],
            'language': 'zh',
            'schema': schema
        }
        
        try:
            res = llm_service.call_structured(payload)
            relations_raw = res.get('relations', [])
        except Exception as e:
            logger.warning(f"LLM关系提取失败: {e}")
            return []
        
        # 后处理：过滤和规范化
        relations = []
        for r in relations_raw:
            # 1. 映射关系类型到枚举
            rel_type = self.normalize_relation(r.get('relation', ''))
            if not rel_type:
                continue
            
            # 2. 检查置信度阈值
            confidence = r.get('confidence', 1.0)
            if confidence < self.conf_threshold:
                continue
            
            # 3. 检查head/tail是否在句子中
            head = r.get('head', '').strip()
            tail = r.get('tail', '').strip()
            if not head or not tail:
                continue
            
            # 简单对齐检查：head和tail应该在句子中出现
            if head not in sent and tail not in sent:
                continue
            
            relations.append({
                'src_name': head,
                'tgt_name': tail,
                'type': rel_type,
                'confidence': confidence,
                'evidence': chunk_id
            })
        
        return relations

    @staticmethod
    def _dedup_concepts(concepts: list[dict]) -> list[dict]:
        """概念去重。
        
        Args:
            concepts: 概念列表
            
        Returns:
            去重后的概念列表
        """
        seen = {}
        for c in concepts:
            name = c["name"]
            if name in seen:
                # 合并mentions
                seen[name]["mentions"].extend(c["mentions"])
            else:
                seen[name] = c
        
        # 去重mentions
        for c in seen.values():
            c["mentions"] = list(set(c["mentions"]))
        
        return list(seen.values())

    @staticmethod
    def _dedup_relations(relations: list[dict]) -> list[dict]:
        """关系去重。
        
        Args:
            relations: 关系列表
            
        Returns:
            去重后的关系列表
        """
        seen = set()
        unique = []
        
        for r in relations:
            key = (r["src_name"], r["type"], r["tgt_name"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        return unique

    @staticmethod
    def normalize_relation(rel_text: str) -> str | None:
        """将关系文本映射到枚举类型。
        
        Args:
            rel_text: 关系文本
            
        Returns:
            规范化的关系类型，如果无法映射返回None
        """
        rel_lower = rel_text.lower().strip()
        
        # 直接匹配枚举
        if rel_text.upper() in RELATION_TYPES:
            return rel_text.upper()
        
        # 查找映射表
        if rel_lower in RELATION_MAPPING:
            return RELATION_MAPPING[rel_lower]
        
        # 无法映射
        return None
