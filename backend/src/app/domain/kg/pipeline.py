#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG Pipeline - 工程化分层流水线统一接口
按照 IMPROOVE_GUIDE.md 的工程化分层设计：Builder → Normalizer → Idempotent → Store → Merger → Service
"""

import logging
from typing import Dict, Any, Optional

from .schemas import KGPipelineInput, KGPipelineOutput, KGDict
from .ids import generate_section_id, generate_content_hash
from .builder import KGBuilderFactory, BaseKGBuilder
from .normalizer import KGNormalizer
from .idempotent import KGIdempotentProcessor, generate_book_id
from .store import create_kg_store, BaseKGStore
from .merger import KGMerger
from .service import create_kg_service, BaseKGService
from .evaluator import KGEvaluator
from .thresholds import KGThresholds


logger = logging.getLogger(__name__)


class KGPipeline:
    """
    工程化KG流水线
    
    分层架构：
    1. Builder: LLM抽取 → JSON Schema
    2. Normalizer: 别名/词形/同义词处理  
    3. Idempotent: 幂等ID生成与查重
    4. Store: Neo4j写入，唯一约束
    5. Merger: 整书级合并去重
    6. Service: 查询API服务层
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 初始化各层组件
        self.builder: BaseKGBuilder = KGBuilderFactory.create_builder(
            self.config.get("builder_type", "llm")
        )
        self.normalizer = KGNormalizer()
        self.idempotent_processor = KGIdempotentProcessor()
        self.store: BaseKGStore = create_kg_store(
            self.config.get("store_type", "neo4j")
        )
        self.merger = KGMerger(self.normalizer)
        self.service: BaseKGService = create_kg_service(
            self.config.get("service_type", "neo4j")
        )
        
        # 保持向后兼容的组件
        self.evaluator = KGEvaluator()
        self.thresholds = KGThresholds(config)

    def run_one_subchapter_new(self, input_data: KGPipelineInput) -> KGPipelineOutput:
        """
        新的工程化流水线：处理单个小节
        
        流程：Builder → Normalizer → Idempotent → Store → Evaluation
        """
        try:
            # 生成基础信息
            section_id = generate_section_id(input_data.topic, input_data.chapter_title, input_data.subchapter_title)
            content_hash = generate_content_hash(input_data.content)
            
            self.logger.info(f"开始工程化KG流水线处理: {input_data.subchapter_title}")
            
            # 1. Builder: LLM抽取 → JSON Schema
            context = {
                "topic": input_data.topic,
                "language": input_data.language,
                "chapter_title": input_data.chapter_title,
                "subchapter_title": input_data.subchapter_title,
                "keywords": input_data.keywords,
                "section_id": section_id,
                "scope": generate_book_id(input_data.topic, input_data.language)
            }
            
            raw_kg = self.builder.build_kg(input_data.content, context)
            self.logger.debug(f"Builder完成: {raw_kg.total_nodes} 节点, {raw_kg.total_edges} 边")
            
            # 2. Normalizer: 别名/词形/同义词处理
            normalized_kg = self.normalizer.normalize_kg_dict(raw_kg, context)
            self.logger.debug(f"Normalizer完成: {normalized_kg.total_nodes} 节点, {normalized_kg.total_edges} 边")
            
            # 3. Idempotent: 幂等ID生成与查重
            idempotent_kg = self.idempotent_processor.process_kg(normalized_kg, context)
            self.logger.debug(f"Idempotent完成: {idempotent_kg.total_nodes} 节点, {idempotent_kg.total_edges} 边")
            
            # 4. 应用阈值过滤（保持兼容）
            filtered_kg = self._apply_thresholds_new(idempotent_kg)
            self.logger.debug(f"Thresholds完成: {filtered_kg.total_nodes} 节点, {filtered_kg.total_edges} 边")
            
            # 5. Store: Neo4j写入，唯一约束
            store_stats = self.store.store_kg(filtered_kg, context)
            self.logger.debug(f"Store完成: {store_stats}")
            
            # 6. Evaluation: 质量评估（保持兼容）
            insights = self._evaluate_kg_new(filtered_kg, input_data)
            
            return KGPipelineOutput(
                section_id=section_id,
                content_hash=content_hash,
                kg_part=self._kg_dict_to_legacy_format(filtered_kg),  # 转换为旧格式保持兼容
                insights=insights,
                store_stats=store_stats,
            )
            
        except Exception as e:
            self.logger.error(f"工程化KG流水线处理失败: {e}")
            return KGPipelineOutput(
                section_id="",
                content_hash="",
                kg_part={"nodes": [], "edges": [], "hierarchy": "", "total_nodes": 0, "total_edges": 0, "chapters_covered": []},
                insights={},
                store_stats={"success": False, "error": str(e)},
            )
    
    def merge_book_kg(self, section_results: list, book_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        整书级KG合并
        
        Args:
            section_results: [(section_id, KGDict), ...] 小节结果列表
            book_context: 整书上下文
            
        Returns:
            Dict: 合并结果统计
        """
        try:
            self.logger.info(f"开始整书KG合并: {len(section_results)} 个小节")
            
            # 使用Merger进行合并
            merged_kg = self.merger.merge_book_kg(section_results, book_context)
            
            # 存储整书KG
            store_stats = self.store.store_kg(merged_kg, book_context)
            
            # 计算合并统计
            merge_stats = self.merger.calculate_merge_stats(section_results, merged_kg)
            
            return {
                "book_id": book_context.get("book_id"),
                "merged_kg": merged_kg,
                "store_stats": store_stats,
                "merge_stats": merge_stats,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"整书KG合并失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _apply_thresholds_new(self, kg_data: KGDict) -> KGDict:
        """应用阈值过滤（新版本）"""
        try:
            # 转换为旧格式以使用现有的阈值逻辑
            legacy_format = self._kg_dict_to_legacy_format(kg_data)
            filtered_legacy = self.thresholds.apply_thresholds(legacy_format)
            
            # 转换回新格式
            return self._legacy_format_to_kg_dict(filtered_legacy)
        except Exception as e:
            self.logger.error(f"应用阈值失败: {e}")
            return kg_data
    
    def _evaluate_kg_new(self, kg_data: KGDict, input_data: KGPipelineInput) -> Dict[str, Any]:
        """KG质量评估（新版本）"""
        try:
            # 转换为旧格式以使用现有的评估逻辑
            legacy_format = self._kg_dict_to_legacy_format(kg_data)
            return self.evaluator.evaluate_kg(legacy_format, input_data)
        except Exception as e:
            self.logger.error(f"KG评估失败: {e}")
            return {}
    
    def _kg_dict_to_legacy_format(self, kg_data: KGDict) -> Dict[str, Any]:
        """将KGDict转换为旧格式"""
        return {
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.type,
                    "desc": node.desc,
                    "aliases": node.aliases,
                    "scope": node.scope
                }
                for node in kg_data.nodes
            ],
            "edges": [
                {
                    "rid": edge.rid,
                    "type": edge.type,
                    "source": edge.source,
                    "target": edge.target,
                    "desc": edge.desc,
                    "confidence": edge.confidence,
                    "weight": edge.weight,
                    "scope": edge.scope
                }
                for edge in kg_data.edges
            ],
            "hierarchy": kg_data.hierarchy,
            "total_nodes": kg_data.total_nodes,
            "total_edges": kg_data.total_edges,
            "chapters_covered": kg_data.chapters_covered
        }
    
    def _legacy_format_to_kg_dict(self, legacy_data: Dict[str, Any]) -> KGDict:
        """将旧格式转换为KGDict"""
        from .schemas import KGNode, KGEdge
        
        nodes = []
        for node_data in legacy_data.get("nodes", []):
            node = KGNode(
                id=node_data.get("id", ""),
                name=node_data.get("name", ""),
                type=node_data.get("type", "Concept"),
                desc=node_data.get("desc", ""),
                aliases=node_data.get("aliases", []),
                scope=node_data.get("scope", ""),
                created_at=None,
                updated_at=None
            )
            nodes.append(node)
        
        edges = []
        for edge_data in legacy_data.get("edges", []):
            edge = KGEdge(
                rid=edge_data.get("rid", ""),
                type=edge_data.get("type", "RELATED_TO"),
                source=edge_data.get("source", ""),
                target=edge_data.get("target", ""),
                desc=edge_data.get("desc", ""),
                confidence=edge_data.get("confidence", 0.8),
                weight=edge_data.get("weight", 1.0),
                scope=edge_data.get("scope", ""),
                src_section="",
                created_at=None
            )
            edges.append(edge)
        
        return KGDict(
            nodes=nodes,
            edges=edges,
            hierarchy=legacy_data.get("hierarchy", ""),
            total_nodes=len(nodes),
            total_edges=len(edges),
            chapters_covered=legacy_data.get("chapters_covered", [])
        )

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
            from ..agents.kg_builder import KGBuilder

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


