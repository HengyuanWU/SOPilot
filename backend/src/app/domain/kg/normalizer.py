#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Dict, List, Any

from .ids import generate_concept_id, slug
from .schemas import NodeDict, EdgeDict, KGDict


logger = logging.getLogger(__name__)


class KGNormalizer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def normalize_kg_dict(self, raw_kg: 'KGDict', context: Dict[str, Any]) -> 'KGDict':
        """
        标准化KGDict格式的数据（新版本）
        
        Args:
            raw_kg: 原始KG数据
            context: 上下文信息
            
        Returns:
            KGDict: 标准化后的KG数据
        """
        try:
            # 标准化节点
            normalized_nodes = []
            for node in raw_kg.nodes:
                normalized_name = self._normalize_name(node.name)
                if normalized_name:
                    # 创建标准化的节点
                    from .schemas import KGNode
                    normalized_node = KGNode(
                        id=node.id,
                        name=normalized_name,
                        type=node.type,
                        desc=self._normalize_description(node.desc),
                        aliases=self._normalize_aliases(node.aliases, normalized_name),
                        scope=node.scope,
                        created_at=node.created_at,
                        updated_at=node.updated_at
                    )
                    normalized_nodes.append(normalized_node)
            
            # 标准化边（基本上保持不变，但可以添加描述标准化）
            normalized_edges = []
            for edge in raw_kg.edges:
                from .schemas import KGEdge
                normalized_edge = KGEdge(
                    rid=edge.rid,
                    type=edge.type,
                    source=edge.source,
                    target=edge.target,
                    desc=self._normalize_description(edge.desc),
                    confidence=edge.confidence,
                    weight=edge.weight,
                    scope=edge.scope,
                    src_section=edge.src_section,
                    created_at=edge.created_at
                )
                normalized_edges.append(normalized_edge)
            
            from .schemas import KGDict
            return KGDict(
                nodes=normalized_nodes,
                edges=normalized_edges,
                hierarchy=raw_kg.hierarchy,
                total_nodes=len(normalized_nodes),
                total_edges=len(normalized_edges),
                chapters_covered=raw_kg.chapters_covered
            )
            
        except Exception as e:
            self.logger.error(f"KG标准化失败: {e}")
            return raw_kg
    
    def _normalize_name(self, name: str) -> str:
        """标准化名称"""
        if not name:
            return ""
        
        # 基本清理
        normalized = name.strip()
        
        # 移除多余空格
        normalized = ' '.join(normalized.split())
        
        # TODO: 可以添加更多标准化规则
        # - 统一术语
        # - 缩写展开
        # - 大小写标准化
        
        return normalized
    
    def _normalize_description(self, desc: str) -> str:
        """标准化描述"""
        if not desc:
            return ""
        
        # 基本清理
        normalized = desc.strip()
        
        # 移除多余空格和换行
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _normalize_aliases(self, aliases: List[str], canonical_name: str) -> List[str]:
        """标准化别名列表"""
        if not aliases:
            return []
        
        normalized_aliases = []
        for alias in aliases:
            if alias and alias.strip() and alias.strip() != canonical_name:
                normalized = self._normalize_name(alias)
                if normalized and normalized not in normalized_aliases:
                    normalized_aliases.append(normalized)
        
        return sorted(normalized_aliases)

    def normalize_kg(self, raw_kg: Dict[str, Any], topic: str, chapter_title: str, subchapter_title: str, section_id: str) -> KGDict:
        try:
            current_time = datetime.utcnow().isoformat()
            normalized_nodes: List[NodeDict] = []
            for raw_node in raw_kg.get("nodes", []):
                if not isinstance(raw_node, dict):
                    continue
                if "id" in raw_node and "type" in raw_node:
                    normalized_nodes.append(raw_node)
                    continue
                node_name = raw_node.get("name", "")
                if not node_name:
                    continue
                normalized_nodes.append({
                    "id": generate_concept_id(node_name, topic, chapter_title, subchapter_title),
                    "type": "concept",
                    "name": node_name,
                    "description": raw_node.get("description", ""),
                    "canonical_key": slug(node_name),
                    "aliases": raw_node.get("aliases", []),
                    "chapter": chapter_title,
                    "subchapter": subchapter_title,
                    "score": raw_node.get("score", 1.0),
                    "source": "llm_generated",
                    "created_at": current_time,
                    "updated_at": current_time,
                })

            normalized_edges: List[EdgeDict] = []
            for raw_edge in raw_kg.get("edges", []):
                if not isinstance(raw_edge, dict):
                    continue
                if "id" in raw_edge and "source_id" in raw_edge and "target_id" in raw_edge:
                    normalized_edges.append(raw_edge)
                    continue
                source_name = raw_edge.get("source", "")
                target_name = raw_edge.get("target", "")
                edge_type = raw_edge.get("type", "MENTIONS").upper()
                if not (source_name and target_name):
                    continue
                source_id = generate_concept_id(source_name, topic, chapter_title, subchapter_title)
                target_id = generate_concept_id(target_name, topic, chapter_title, subchapter_title)
                edge_id = f"{edge_type}:{source_id}->{target_id}"
                normalized_edges.append({
                    "id": edge_id,
                    "type": edge_type,
                    "source_id": source_id,
                    "target_id": target_id,
                    "source_name": source_name,
                    "target_name": target_name,
                    "weight": raw_edge.get("weight", 1.0),
                    "confidence": raw_edge.get("confidence", 0.8),
                    "evidence": raw_edge.get("evidence", f"从文本中抽取的关系: {source_name} -> {target_name}"),
                    "chapter": chapter_title,
                    "src": section_id,
                    "created_at": current_time,
                    "updated_at": current_time,
                })

            return {
                "nodes": normalized_nodes,
                "edges": normalized_edges,
                "hierarchy": raw_kg.get("hierarchy", ""),
                "total_nodes": len(normalized_nodes),
                "total_edges": len(normalized_edges),
                "chapters_covered": [chapter_title],
            }
        except Exception as e:
            logger.error(f"KG 标准化失败: {e}")
            return {"nodes": [], "edges": [], "hierarchy": "", "total_nodes": 0, "total_edges": 0, "chapters_covered": []}

