#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG Merger - 整书级合并，跨节归并/去重
工程化分层设计中的第五层：将多个小节的KG合并成整书级别的知识图谱
"""

import logging
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

from .schemas import KGNode, KGEdge, KGDict
from .normalizer import KGNormalizer


logger = logging.getLogger(__name__)


class KGMerger:
    """KG合并器 - 负责整书级别的知识图谱合并"""
    
    def __init__(self, normalizer: KGNormalizer = None):
        self.normalizer = normalizer or KGNormalizer()
        self.logger = logging.getLogger(__name__)
    
    def merge_book_kg(self, section_kgs: List[Tuple[str, KGDict]], book_context: Dict[str, Any]) -> KGDict:
        """
        合并多个小节的KG为整书KG
        
        Args:
            section_kgs: [(section_id, kg_dict), ...] 小节KG列表
            book_context: 整书上下文信息 (book_id, topic等)
            
        Returns:
            KGDict: 合并后的整书KG
        """
        try:
            if not section_kgs:
                self.logger.warning("没有小节KG需要合并")
                return self._create_empty_book_kg(book_context)
            
            self.logger.info(f"开始合并 {len(section_kgs)} 个小节的KG")
            
            # 收集所有节点和边
            all_nodes = []
            all_edges = []
            chapters_covered = set()
            
            for section_id, kg_data in section_kgs:
                all_nodes.extend(kg_data.nodes)
                all_edges.extend(kg_data.edges)
                chapters_covered.update(kg_data.chapters_covered)
            
            # 节点合并和去重
            merged_nodes = self._merge_nodes(all_nodes, book_context)
            
            # 边合并和去重
            merged_edges = self._merge_edges(all_edges, merged_nodes, book_context)
            
            # 创建整书层级结构
            hierarchy = self._build_book_hierarchy(chapters_covered, book_context)
            
            merged_kg = KGDict(
                nodes=merged_nodes,
                edges=merged_edges,
                hierarchy=hierarchy,
                total_nodes=len(merged_nodes),
                total_edges=len(merged_edges),
                chapters_covered=sorted(list(chapters_covered))
            )
            
            self.logger.info(f"KG合并完成: {len(merged_nodes)} 节点, {len(merged_edges)} 边")
            return merged_kg
            
        except Exception as e:
            self.logger.error(f"KG合并失败: {e}")
            return self._create_empty_book_kg(book_context)
    
    def _merge_nodes(self, all_nodes: List[KGNode], book_context: Dict[str, Any]) -> List[KGNode]:
        """合并和去重节点"""
        # 使用名称和类型作为合并键
        node_groups = defaultdict(list)
        
        for node in all_nodes:
            # 标准化名称
            canonical_name = self.normalizer._normalize_name(node.name)
            merge_key = f"{canonical_name}|{node.type}"
            node_groups[merge_key].append(node)
        
        merged_nodes = []
        for merge_key, nodes in node_groups.items():
            merged_node = self._merge_node_group(nodes, book_context)
            if merged_node:
                merged_nodes.append(merged_node)
        
        return merged_nodes
    
    def _merge_node_group(self, nodes: List[KGNode], book_context: Dict[str, Any]) -> KGNode:
        """合并一组相似的节点"""
        if not nodes:
            return None
        
        if len(nodes) == 1:
            # 更新scope为book级别
            node = nodes[0]
            return KGNode(
                id=node.id,
                name=node.name,
                type=node.type,
                desc=node.desc,
                aliases=node.aliases,
                scope=book_context.get("book_id", node.scope),
                created_at=node.created_at,
                updated_at=node.updated_at
            )
        
        # 多个节点需要合并
        # 选择最详细的描述
        best_desc = ""
        for node in nodes:
            if node.desc and len(node.desc) > len(best_desc):
                best_desc = node.desc
        
        # 合并别名
        all_aliases = set()
        for node in nodes:
            if node.aliases:
                all_aliases.update(node.aliases)
        
        # 使用第一个节点作为基础
        base_node = nodes[0]
        
        return KGNode(
            id=base_node.id,  # 保持第一个节点的ID
            name=base_node.name,
            type=base_node.type,
            desc=best_desc,
            aliases=sorted(list(all_aliases)),
            scope=book_context.get("book_id", base_node.scope),
            created_at=base_node.created_at,
            updated_at=base_node.updated_at
        )
    
    def _merge_edges(self, all_edges: List[KGEdge], merged_nodes: List[KGNode], book_context: Dict[str, Any]) -> List[KGEdge]:
        """合并和去重边"""
        # 创建节点ID映射
        node_id_set = {node.id for node in merged_nodes}
        
        # 去重边（基于源、目标、类型）
        edge_fingerprints = set()
        merged_edges = []
        
        for edge in all_edges:
            # 跳过无效边（节点不存在）
            if edge.source not in node_id_set or edge.target not in node_id_set:
                continue
            
            # 创建边指纹
            fingerprint = f"{edge.source}|{edge.target}|{edge.type}"
            
            if fingerprint in edge_fingerprints:
                continue
            
            edge_fingerprints.add(fingerprint)
            
            # 更新边的scope为book级别
            merged_edge = KGEdge(
                rid=edge.rid,
                type=edge.type,
                source=edge.source,
                target=edge.target,
                desc=edge.desc,
                confidence=edge.confidence,
                weight=edge.weight,
                scope=book_context.get("book_id", edge.scope),
                src_section=edge.src_section,  # 保留原始section信息
                created_at=edge.created_at
            )
            
            merged_edges.append(merged_edge)
        
        return merged_edges
    
    def _build_book_hierarchy(self, chapters_covered: Set[str], book_context: Dict[str, Any]) -> str:
        """构建整书层级结构"""
        if not chapters_covered:
            return ""
        
        topic = book_context.get("topic", "Unknown Topic")
        book_id = book_context.get("book_id", "unknown_book")
        
        hierarchy_parts = [
            f"Book: {topic} (ID: {book_id})",
            f"Chapters: {', '.join(sorted(chapters_covered))}",
            f"Total Chapters: {len(chapters_covered)}"
        ]
        
        return "\n".join(hierarchy_parts)
    
    def _create_empty_book_kg(self, book_context: Dict[str, Any]) -> KGDict:
        """创建空的整书KG"""
        return KGDict(
            nodes=[],
            edges=[],
            hierarchy=f"Book: {book_context.get('topic', 'Unknown')} (Empty)",
            total_nodes=0,
            total_edges=0,
            chapters_covered=[]
        )
    
    def merge_incremental(self, existing_kg: KGDict, new_section_kg: KGDict, context: Dict[str, Any]) -> KGDict:
        """
        增量合并新的小节KG到现有的整书KG中
        
        Args:
            existing_kg: 现有的整书KG
            new_section_kg: 新的小节KG
            context: 上下文信息
            
        Returns:
            KGDict: 更新后的整书KG
        """
        try:
            self.logger.info("开始增量合并KG")
            
            # 将现有KG和新KG组合
            section_kgs = [
                ("existing", existing_kg),
                (context.get("section_id", "new"), new_section_kg)
            ]
            
            # 使用完整合并逻辑
            return self.merge_book_kg(section_kgs, context)
            
        except Exception as e:
            self.logger.error(f"增量合并失败: {e}")
            return existing_kg  # 返回原有KG
    
    def calculate_merge_stats(self, section_kgs: List[Tuple[str, KGDict]], merged_kg: KGDict) -> Dict[str, Any]:
        """计算合并统计信息"""
        try:
            # 原始统计
            original_nodes = sum(kg.total_nodes for _, kg in section_kgs)
            original_edges = sum(kg.total_edges for _, kg in section_kgs)
            
            # 合并后统计
            merged_nodes = merged_kg.total_nodes
            merged_edges = merged_kg.total_edges
            
            # 计算去重比例
            node_dedup_ratio = (original_nodes - merged_nodes) / original_nodes if original_nodes > 0 else 0
            edge_dedup_ratio = (original_edges - merged_edges) / original_edges if original_edges > 0 else 0
            
            return {
                "original_sections": len(section_kgs),
                "original_nodes": original_nodes,
                "original_edges": original_edges,
                "merged_nodes": merged_nodes,
                "merged_edges": merged_edges,
                "node_dedup_ratio": round(node_dedup_ratio, 3),
                "edge_dedup_ratio": round(edge_dedup_ratio, 3),
                "chapters_covered": len(merged_kg.chapters_covered)
            }
            
        except Exception as e:
            self.logger.error(f"计算合并统计失败: {e}")
            return {}


class ConceptMerger:
    """概念合并器 - 专门处理概念节点的同义词合并"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def merge_similar_concepts(self, concepts: List[KGNode], similarity_threshold: float = 0.8) -> List[KGNode]:
        """
        合并相似的概念节点
        
        Args:
            concepts: 概念节点列表
            similarity_threshold: 相似度阈值
            
        Returns:
            List[KGNode]: 合并后的概念节点列表
        """
        # TODO: 实现基于语义相似度的概念合并
        # 可以使用词向量、编辑距离等方法
        self.logger.info("ConceptMerger尚未实现语义相似度合并")
        return concepts
    
    def detect_synonyms(self, concept_names: List[str]) -> List[List[str]]:
        """
        检测同义词组
        
        Args:
            concept_names: 概念名称列表
            
        Returns:
            List[List[str]]: 同义词组列表
        """
        # TODO: 实现同义词检测
        # 可以使用预训练的同义词词典、WordNet等
        self.logger.info("ConceptMerger同义词检测尚未实现")
        return [[name] for name in concept_names]  # 暂时返回单独的组