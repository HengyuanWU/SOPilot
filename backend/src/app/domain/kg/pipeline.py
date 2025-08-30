#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
域层 KGPipeline 实现（从 modules 迁移并对齐域层依赖）
"""

import logging
from typing import Dict, Any, Optional

from .schemas import KGPipelineInput, KGPipelineOutput, KGDict
from .ids import generate_section_id, generate_content_hash
from .normalizer import KGNormalizer
from .evaluator import KGEvaluator
from .thresholds import KGThresholds
from .store import KGStore
# 延迟导入以避免循环依赖


logger = logging.getLogger(__name__)


class KGPipeline:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.normalizer = KGNormalizer()
        self.evaluator = KGEvaluator()
        self.thresholds = KGThresholds(config)
        self.store: Optional[KGStore] = None
        self._initialize_store()
        self.logger = logging.getLogger(__name__)

    def _initialize_store(self):
        try:
            # 阶段4：改为使用基础设施层的 Neo4j 存储（延迟导入）
            from app.infrastructure.graph_store import create_neo4j_store
            store = create_neo4j_store(self.config)
            if store:
                self.store = store
                logger.info("KG Pipeline 使用 Neo4j 存储（infrastructure）")
            else:
                from .store import MemoryKGStore

                self.store = MemoryKGStore()
                logger.info("KG Pipeline 使用 Memory 存储")
        except Exception as e:
            logger.error(f"初始化 KG 存储失败: {e}")
            from .store import MemoryKGStore

            self.store = MemoryKGStore()
            logger.info("回退到内存存储")

    def run_one_subchapter(self, input_data: KGPipelineInput) -> KGPipelineOutput:
        try:
            section_id = generate_section_id(input_data.topic, input_data.chapter_title, input_data.subchapter_title)
            content_hash = generate_content_hash(input_data.content)
            logger.info(f"开始处理子章节: {input_data.subchapter_title}")
            logger.debug(f"Section ID: {section_id}, Content Hash: {content_hash}")
            raw_kg = self._build_raw_kg(input_data)
            normalized_kg = self.normalizer.normalize_kg(
                raw_kg, input_data.topic, input_data.chapter_title, input_data.subchapter_title, section_id
            )
            filtered_kg = self._apply_thresholds(normalized_kg)
            store_stats = self._store_kg(filtered_kg, section_id)
            insights = self._evaluate_kg(filtered_kg, input_data)
            return KGPipelineOutput(
                section_id=section_id,
                content_hash=content_hash,
                kg_part=filtered_kg,
                insights=insights,
                store_stats=store_stats,
            )
        except Exception as e:
            logger.error(f"KG Pipeline 处理失败: {e}")
            return KGPipelineOutput(
                section_id="",
                content_hash="",
                kg_part={"nodes": [], "edges": [], "hierarchy": "", "total_nodes": 0, "total_edges": 0, "chapters_covered": []},
                insights={},
                store_stats={"success": False, "error": str(e)},
            )

    def _build_raw_kg(self, input_data: KGPipelineInput) -> Dict[str, Any]:
        try:
            from app.domain.agents.kg_builder import KGBuilder

            kg_state = {
                "topic": input_data.topic,
                "language": input_data.language,
                "chapter_title": input_data.chapter_title,
                "content": {input_data.subchapter_title: input_data.content},
                "keywords": input_data.keywords,
                "subchapter_keywords_map": {input_data.subchapter_title: input_data.keywords},
                "chapter_keywords_map": {input_data.chapter_title: input_data.keywords},
            }
            kg_builder = KGBuilder()
            result_state = kg_builder.execute(kg_state)
            kg_data = result_state.get("knowledge_graphs", {}).get(input_data.subchapter_title, {})
            if not kg_data:
                fallback = result_state.get("kg", {})
                if fallback:
                    kg_data = {
                        "nodes": fallback.get("nodes", []),
                        "edges": fallback.get("edges", []),
                        "hierarchy": fallback.get("hierarchy", ""),
                    }
            return kg_data
        except Exception as e:
            logger.error(f"RAW KG 构建失败: {e}")
            return {"nodes": [], "edges": [], "hierarchy": ""}

    def _apply_thresholds(self, kg: KGDict) -> KGDict:
        try:
            edges = kg.get("edges", [])
            filtered_edges = self.thresholds.filter_edges_for_storage(edges)
            filtered_kg = kg.copy()
            filtered_kg["edges"] = filtered_edges
            filtered_kg["total_edges"] = len(filtered_edges)
            return filtered_kg
        except Exception as e:
            logger.error(f"阈值过滤失败: {e}")
            return kg

    def _store_kg(self, kg: KGDict, section_id: str) -> Dict[str, Any]:
        stats = {"attempted": False, "success": False, "nodes_written": 0, "edges_written": 0, "edges_deleted": 0, "error": None}
        if not self.store:
            stats["error"] = "存储后端未初始化"
            return stats
        try:
            stats["attempted"] = True
            
            # B1方案：使用scope进行删除，同时保持兼容性
            scope = f"section:{section_id}"
            
            # 优先使用scope删除，如果不支持则回退到src删除
            try:
                edges_deleted = self.store.delete_edges_by_scope(scope)
            except (AttributeError, NotImplementedError):
                edges_deleted = self.store.delete_edges_by_src(section_id)
            
            stats["edges_deleted"] = edges_deleted
            
            # 写入节点
            nodes_written = 0
            for node in kg.get("nodes", []):
                if self.store.merge_node(node):
                    nodes_written += 1
            stats["nodes_written"] = nodes_written
            
            # 写入边，添加scope和rid信息
            edges_written = 0
            from .ids import generate_relation_rid
            
            for edge in kg.get("edges", []):
                # 为小节视图关系添加scope、rid和src信息
                edge_copy = edge.copy()
                edge_copy["scope"] = scope
                edge_copy["src"] = section_id  # 兼容保留
                
                # 生成rid
                edge_type = edge_copy.get("type", "")
                source_id = edge_copy.get("source_id", "")
                target_id = edge_copy.get("target_id", "")
                edge_copy["rid"] = generate_relation_rid(edge_type, source_id, target_id, scope)
                
                if self.store.merge_edge(edge_copy):
                    edges_written += 1
                    
            stats["edges_written"] = edges_written
            stats["success"] = True
            logger.info(f"KG 存储完成: {nodes_written} 节点, {edges_written} 边, 删除 {edges_deleted} 旧边")
        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"KG 存储失败: {e}")
        return stats

    def _evaluate_kg(self, kg: KGDict, input_data: KGPipelineInput) -> Dict[str, Any]:
        try:
            structure = self.evaluator.analyze_graph_structure(kg)
            relationships = self.evaluator.extract_node_relationships(kg)
            chapters = [{"title": input_data.chapter_title, "subchapters": [{"title": input_data.subchapter_title}]}]
            coverage = self.evaluator.assess_knowledge_coverage(kg, chapters, input_data.keywords)
            return {
                "kg_structure": structure,
                "node_relationships": relationships,
                "knowledge_coverage": coverage,
                "kg_summary": self._generate_summary(structure, relationships, coverage),
            }
        except Exception as e:
            logger.error(f"KG 评估失败: {e}")
            return {}

    def _generate_summary(self, structure: Dict[str, Any], relationships: Dict[str, Any], coverage: Dict[str, Any]) -> str:
        try:
            total_nodes = structure.get("total_nodes", 0)
            total_edges = structure.get("total_edges", 0)
            connectivity = structure.get("connectivity_score", 0.0)
            coverage_score = coverage.get("coverage_score", 0.0)
            return (
                f"知识图谱构建摘要：\n- 节点数量: {total_nodes}\n- 边数量: {total_edges}\n- 连通性分数: {connectivity:.2f}\n- 覆盖度分数: {coverage_score:.2f}"
            )
        except Exception:
            logger.error("生成摘要失败", exc_info=True)
            return "摘要生成失败"


