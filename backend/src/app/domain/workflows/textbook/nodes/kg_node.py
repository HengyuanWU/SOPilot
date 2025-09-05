#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.domain.kg import KGPipeline, KGPipelineInput, generate_section_id
from app.domain.kg.merge import KGMerger
from app.core.concurrency import get_concurrency_config

logger = logging.getLogger(__name__)


def kg_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if state.get("error"):
            return state
        logger.info("开始执行知识图谱节点")
        concurrency_config = get_concurrency_config()
        max_workers = concurrency_config["kg_builder"]["max_workers"]

        topic = state.get("topic", "未知主题")
        language = state.get("language", "中文")
        chapters = state.get("chapters", [])
        content = state.get("content", {})
        validation_results = state.get("validation_results", {})
        subchapter_keywords_map = state.get("subchapter_keywords_map", {})

        passed_subchapters: List[Tuple[str, str, str, List[str]]] = []
        for chapter in chapters:
            chapter_title = chapter["title"]
            for subchapter in chapter.get("subchapters", []):
                subchapter_title = subchapter["title"]
                validation_result = validation_results.get(subchapter_title, {})
                if validation_result.get("is_passed", False):
                    subchapter_content = content.get(subchapter_title, "")
                    subchapter_keywords = subchapter_keywords_map.get(subchapter_title, [])
                    if subchapter_content:
                        passed_subchapters.append(
                            (chapter_title, subchapter_title, subchapter_content, subchapter_keywords)
                        )

        if not passed_subchapters:
            logger.warning("没有通过验证的子章节，跳过知识图谱构建")
            result_state = state.copy()
            result_state["cross_agent_insights"] = result_state.get("cross_agent_insights", {})
            result_state["cross_agent_insights"]["kg_builder"] = {
                "kg_structure": {"total_nodes": 0, "total_edges": 0},
                "node_relationships": {"relationship_types": {}, "relation_richness": 0.0},
                "knowledge_coverage": {"coverage_score": 0.0},
                "kg_summary": "没有通过验证的内容，跳过知识图谱构建",
            }
            # 记录通过统计，帮助前端/运维快速定位
            try:
                vres = result_state.get("validation_results", {}) or {}
                total = len(vres)
                passed = sum(1 for v in vres.values() if v.get("is_passed", False))
                stats = result_state.get("processing_stats", {}) or {}
                stats["kg_builder"] = {"passed_subchapters": passed, "total_subchapters": total}
                result_state["processing_stats"] = stats
            except Exception:
                pass
            return result_state

        logger.info(f"开始为 {len(passed_subchapters)} 个通过验证的子章节构建知识图谱")
        kg_pipeline = KGPipeline(state.get("config", {}))

        kg_parts: Dict[str, Dict[str, Any]] = {}
        section_ids: List[str] = []
        all_insights: List[Dict[str, Any]] = []
        all_store_stats: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_subchapter = {}
            for chapter_title, subchapter_title, subchapter_content, subchapter_keywords in passed_subchapters:
                pipeline_input = KGPipelineInput(
                    topic=topic,
                    chapter_title=chapter_title,
                    subchapter_title=subchapter_title,
                    content=subchapter_content,
                    keywords=subchapter_keywords,
                    language=language,
                )
                future = executor.submit(kg_pipeline.run_one_subchapter, pipeline_input)
                future_to_subchapter[future] = subchapter_title

            for future in as_completed(future_to_subchapter):
                subchapter_title = future_to_subchapter[future]
                try:
                    pipeline_output = future.result()
                    kg_parts[subchapter_title] = pipeline_output.kg_part
                    all_insights.append(pipeline_output.insights)
                    all_store_stats.append(pipeline_output.store_stats)
                    if getattr(pipeline_output, "section_id", ""):
                        section_ids.append(pipeline_output.section_id)
                    logger.info(f"子章节 '{subchapter_title}' 知识图谱构建完成")
                except Exception as e:
                    logger.error(f"子章节 '{subchapter_title}' 知识图谱构建失败: {e}")
                    kg_parts[subchapter_title] = {
                        "nodes": [],
                        "edges": [],
                        "hierarchy": "",
                        "total_nodes": 0,
                        "total_edges": 0,
                        "chapters_covered": [],
                    }

        # 暂时跳过整书级合并，因为数据已经在Neo4j中
        # book_graph_node会处理整书级的数据组织
        logger.info(f"跳过内存整书级合并，数据已存储到Neo4j，section_ids: {section_ids}")
        
        # 生成book_id
        from app.domain.kg.ids import generate_book_id
        book_id = generate_book_id(topic, state.get("thread_id", ""))
        logger.info(f"生成book_id: {book_id}")
        
        # 使用旧的合并方式为兼容性
        merger = KGMerger()
        merged_kg = merger.merge_multiple_kgs(list(kg_parts.values()))

        from app.domain.kg import KGEvaluator  # 仅用于类型与结构
        from app.domain.kg.schemas import KGDict
        
        # 确保merged_kg是字典格式，兼容KGDict和普通字典
        if isinstance(merged_kg, KGDict):
            # 将KGDict转换为字典格式供评估器使用
            merged_kg_dict = {
                "nodes": [{"id": node.id, "name": node.name, "type": node.type, 
                          "desc": node.desc, "aliases": node.aliases} for node in merged_kg.nodes],
                "edges": [{"id": edge.id, "src": edge.src, "tgt": edge.tgt, 
                          "type": edge.type, "desc": edge.desc} for edge in merged_kg.edges]
            }
        else:
            merged_kg_dict = merged_kg
            
        evaluator = KGEvaluator()
        structure_analysis = evaluator.analyze_graph_structure(merged_kg_dict)
        relationship_analysis = evaluator.extract_node_relationships(merged_kg_dict)
        all_keywords: List[str] = []
        for insight in all_insights:
            coverage = insight.get("knowledge_coverage", {})
            all_keywords.extend(coverage.get("covered_keywords", []))
        coverage_analysis = evaluator.assess_knowledge_coverage(merged_kg_dict, chapters, all_keywords)

        aggregated_insights = {
            "kg_structure": structure_analysis,
            "node_relationships": relationship_analysis,
            "knowledge_coverage": coverage_analysis,
            "kg_summary": f"知识图谱构建完成：{structure_analysis.get('total_nodes', 0)} 个节点，{structure_analysis.get('total_edges', 0)} 条边",
        }

        aggregated_stats = {
            "total_subchapters_processed": len(all_store_stats),
            "successful_writes": sum(1 for s in all_store_stats if s.get("success")),
            "total_nodes_written": sum(s.get("nodes_written", 0) for s in all_store_stats),
            "total_edges_written": sum(s.get("edges_written", 0) for s in all_store_stats),
            "total_edges_deleted": sum(s.get("edges_deleted", 0) for s in all_store_stats),
            "success_rate": (
                sum(1 for s in all_store_stats if s.get("success")) / len(all_store_stats)
                if all_store_stats
                else 0.0
            ),
        }

        result_state = state.copy()
        result_state["knowledge_graphs"] = kg_parts
        # 确保传递给book_graph_node的是字典格式
        result_state["merged_knowledge_graph"] = merged_kg_dict
        result_state["cross_agent_insights"] = result_state.get("cross_agent_insights", {})
        result_state["cross_agent_insights"]["kg_builder"] = aggregated_insights
        result_state["kg_store_stats"] = aggregated_stats
        if not section_ids:
            # 管线异常或未产生 section_id，使用确定性回退生成
            try:
                computed_ids: List[str] = []
                for chapter_title, subchapter_title, _content, _keywords in passed_subchapters:
                    sid = generate_section_id(topic, chapter_title, subchapter_title)
                    computed_ids.append(sid)
                # 去重并回填
                if computed_ids:
                    uniq_ids = list(dict.fromkeys(computed_ids).keys())
                    section_ids = uniq_ids
            except Exception:
                pass

        if section_ids:
            result_state["section_ids"] = section_ids
            if "section_id" not in result_state:
                result_state["section_id"] = section_ids[0]
        
        # 设置book_id到状态中
        if book_id:
            result_state["book_id"] = book_id
            logger.info(f"设置book_id到状态: {book_id}")

        # 记统计
        try:
            stats = result_state.get("processing_stats", {}) or {}
            stats["kg_builder"] = {
                "total_subchapters_processed": len(passed_subchapters),
                "section_ids_count": len(section_ids or []),
            }
            result_state["processing_stats"] = stats
        except Exception:
            pass
        return result_state
    except Exception as e:
        logger.error(f"知识图谱节点执行失败: {e}")
        error_state = state.copy()
        error_state["error"] = f"知识图谱构建失败: {str(e)}"
        return error_state

__all__ = ["kg_node"]

