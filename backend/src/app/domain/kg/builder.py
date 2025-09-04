#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG Builder - LLM抽取 → JSON Schema
工程化分层设计中的第一层：从文本内容抽取结构化知识图谱
"""

import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from .schemas import KGNode, KGEdge, KGDict
from ...services.llm_service import LLMService


logger = logging.getLogger(__name__)


class BaseKGBuilder(ABC):
    """KG构建器基类，支持不同的构建策略"""
    
    @abstractmethod
    def build_kg(self, content: str, context: Dict[str, Any]) -> KGDict:
        """从内容构建知识图谱"""
        pass


class LLMKGBuilder(BaseKGBuilder):
    """基于LLM的知识图谱构建器"""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()
        self.logger = logging.getLogger(__name__)
    
    def build_kg(self, content: str, context: Dict[str, Any]) -> KGDict:
        """
        使用LLM从内容中抽取知识图谱
        
        Args:
            content: 文本内容
            context: 上下文信息 (topic, chapter_title, subchapter_title等)
            
        Returns:
            KGDict: 标准化的知识图谱数据
        """
        try:
            # 使用migration service直接调用LLM
            from ...services.migration_service import migration_helper
            
            # 准备调用参数
            topic = context.get("topic", "")
            keywords = ", ".join(context.get("keywords", []))
            language = context.get("language", "中文")
            
            # 调用LLM生成知识图谱
            raw_content = migration_helper.call_kg_builder(
                topic=topic,
                content_text=content[:3000],  # 限制长度
                keywords=keywords,
                language=language
            )
            
            if not raw_content or raw_content.strip() == "":
                self.logger.warning(f"LLM未能从内容中抽取到KG数据")
                return self._create_empty_kg()
            
            # 解析LLM输出并转换为标准格式
            kg_data = self._parse_llm_output(raw_content, context)
            return self._convert_to_standard_format(kg_data, context)
            
        except Exception as e:
            self.logger.error(f"LLM KG构建失败: {e}")
            return self._create_empty_kg()
    
    def _parse_llm_output(self, raw_content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """解析LLM输出的知识图谱内容"""
        import re
        import hashlib
        from datetime import datetime
        
        current_time = datetime.utcnow().isoformat()
        topic = context.get("topic", "")
        chapter_title = context.get("chapter_title", "")
        subchapter_title = context.get("subchapter_title", "")
        
        def _slug(text: str) -> str:
            cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text)
            return cleaned.strip("_").lower()
        
        def _generate_concept_id(name: str) -> str:
            slug_name = _slug(name)
            content = f"{topic}|{chapter_title}|{subchapter_title}"
            hash_suffix = hashlib.md5(content.encode("utf-8")).hexdigest()[:6]
            return f"concept:{slug_name}:{hash_suffix}"
        
        nodes = []
        edges = []
        
        # 解析节点
        if "### 节点" in raw_content:
            nodes_section = raw_content.split("### 节点")[1].split("###")[0]
            for line in nodes_section.split("\n"):
                if line.strip().startswith("- "):
                    node_text = line.strip()[2:]
                    if ":" in node_text:
                        node_name, node_desc = node_text.split(":", 1)
                        node_name = node_name.strip()
                        node_desc = node_desc.strip()
                        nodes.append({
                            "id": _generate_concept_id(node_name),
                            "type": "concept",
                            "name": node_name,
                            "desc": node_desc,
                            "aliases": [],
                            "chapter": chapter_title,
                            "subchapter": subchapter_title,
                            "created_at": current_time,
                        })
        
        # 解析边
        if "### 关系" in raw_content:
            edges_section = raw_content.split("### 关系")[1].split("###")[0]
            for line in edges_section.split("\n"):
                if line.strip().startswith("- ") and "->" in line and ":" in line:
                    edge_parts, edge_type = line.strip()[2:].split(":", 1)
                    source_name, target_name = edge_parts.split("->", 1)
                    source_name = source_name.strip()
                    target_name = target_name.strip()
                    edge_type = edge_type.strip()
                    
                    source_id = _generate_concept_id(source_name)
                    target_id = _generate_concept_id(target_name)
                    
                    edges.append({
                        "source": source_id,
                        "target": target_id,
                        "type": edge_type.upper(),
                        "desc": f"从文本中抽取的关系: {source_name} -> {target_name}",
                        "confidence": 0.8,
                        "weight": 1.0,
                        "created_at": current_time,
                    })
        
        # 解析层次结构
        hierarchy = ""
        if "### 层次结构" in raw_content:
            hierarchy_section = raw_content.split("### 层次结构")[1]
            hierarchy = hierarchy_section.strip()
        
        return {
            "nodes": nodes,
            "edges": edges,
            "hierarchy": hierarchy,
            "raw_content": raw_content
        }
    
    def _convert_to_standard_format(self, raw_kg: Dict[str, Any], context: Dict[str, Any]) -> KGDict:
        """将原始KG数据转换为标准格式"""
        try:
            from datetime import datetime
            
            nodes = []
            edges = []
            
            # 转换节点
            raw_nodes = raw_kg.get("nodes", [])
            for node_data in raw_nodes:
                if isinstance(node_data, dict):
                    # 处理时间戳
                    created_at = None
                    if node_data.get("created_at"):
                        try:
                            created_at = datetime.fromisoformat(node_data["created_at"].replace('Z', '+00:00'))
                        except:
                            created_at = datetime.utcnow()
                    
                    node = KGNode(
                        id=str(node_data.get("id", "")),
                        name=str(node_data.get("name", "")),
                        type=str(node_data.get("type", "Concept")),
                        desc=str(node_data.get("desc", "")),
                        aliases=node_data.get("aliases", []),
                        scope=context.get("scope") or context.get("topic", ""),
                        created_at=created_at,
                        updated_at=created_at
                    )
                    nodes.append(node)
            
            # 转换边
            raw_edges = raw_kg.get("edges", [])
            for edge_data in raw_edges:
                if isinstance(edge_data, dict):
                    # 处理时间戳
                    created_at = None
                    if edge_data.get("created_at"):
                        try:
                            created_at = datetime.fromisoformat(edge_data["created_at"].replace('Z', '+00:00'))
                        except:
                            created_at = datetime.utcnow()
                    
                    edge = KGEdge(
                        rid="",  # 将在idempotent步骤中生成
                        type=str(edge_data.get("type", "RELATED_TO")),
                        source=str(edge_data.get("source", "")),
                        target=str(edge_data.get("target", "")),
                        desc=str(edge_data.get("desc", "")),
                        confidence=float(edge_data.get("confidence", 0.8)),
                        weight=float(edge_data.get("weight", 1.0)),
                        scope=context.get("scope") or context.get("topic", ""),
                        src_section=context.get("section_id", ""),
                        created_at=created_at
                    )
                    edges.append(edge)
            
            return KGDict(
                nodes=nodes,
                edges=edges,
                hierarchy=raw_kg.get("hierarchy", ""),
                total_nodes=len(nodes),
                total_edges=len(edges),
                chapters_covered=[context.get("chapter_title", "")]
            )
            
        except Exception as e:
            self.logger.error(f"KG格式转换失败: {e}")
            return self._create_empty_kg()
    
    def _create_empty_kg(self) -> KGDict:
        """创建空的KG结构"""
        return KGDict(
            nodes=[],
            edges=[],
            hierarchy="",
            total_nodes=0,
            total_edges=0,
            chapters_covered=[]
        )


class RuleBasedKGBuilder(BaseKGBuilder):
    """基于规则的知识图谱构建器（可选实现）"""
    
    def build_kg(self, content: str, context: Dict[str, Any]) -> KGDict:
        """基于规则从内容中抽取知识图谱"""
        # TODO: 实现基于规则的抽取逻辑
        # 例如：NER + 关系抽取规则
        logger.info("RuleBasedKGBuilder尚未实现")
        return KGDict(
            nodes=[],
            edges=[],
            hierarchy="",
            total_nodes=0,
            total_edges=0,
            chapters_covered=[]
        )


class KGBuilderFactory:
    """KG构建器工厂"""
    
    @staticmethod
    def create_builder(builder_type: str = "llm", **kwargs) -> BaseKGBuilder:
        """创建KG构建器实例"""
        if builder_type.lower() == "llm":
            return LLMKGBuilder(**kwargs)
        elif builder_type.lower() == "rule":
            return RuleBasedKGBuilder(**kwargs)
        else:
            raise ValueError(f"Unknown builder type: {builder_type}")