#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KGBuilder Agent - 知识图谱构建代理（工程化版本）

这个模块实现了新的工程化KG构建流程，使用分层架构：
Builder → Normalizer → Idempotent → Store → Merger → Service

替代了原来的纯LLM文本解析方式。
"""

import logging
from typing import Dict, List, Any
from ..state.textbook_state import TextbookState
from ..kg.pipeline import KGPipeline
from ..kg.schemas import KGPipelineInput, KGPipelineOutput
from ..kg.ids import generate_section_id, generate_book_id

logger = logging.getLogger(__name__)


class KGBuilder:
    """知识图谱构建代理 - 工程化版本"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化KG构建器
        
        Args:
            config: KG流水线配置
        """
        self.config = config or {}
        self.pipeline = KGPipeline(self.config)
        
    def build_knowledge_graph(
        self,
        topic: str,
        content: Dict[str, str],
        keywords: List[str],
        language: str = "中文",
        chapter_title: str = None,
        subchapter_title: str = None,
    ) -> Dict[str, Any]:
        """
        构建知识图谱 - 使用新的工程化流水线
        
        Args:
            topic: 主题
            content: 内容字典 {subchapter: content}
            keywords: 关键词列表
            language: 语言
            chapter_title: 章节标题
            subchapter_title: 小节标题
            
        Returns:
            包含节点、边等信息的知识图谱字典
        """
        try:
            logger.info(f"开始使用工程化流水线构建知识图谱: 主题={topic}, 章节数={len(content)}")
            
            # 新的工程化流水线：只收集存储统计，不再处理具体节点/边数据
            total_nodes_processed = 0
            total_edges_processed = 0
            all_section_ids = []
            
            for subchapter, subchapter_content in content.items():
                current_subchapter_title = subchapter_title or subchapter
                
                # 创建流水线输入
                pipeline_input = KGPipelineInput(
                    topic=topic,
                    chapter_title=chapter_title or "未知章节",
                    subchapter_title=current_subchapter_title,
                    content=subchapter_content,
                    keywords=keywords,
                    language=language
                )
                
                logger.info(f"开始处理子章节: {current_subchapter_title}")
                
                # 运行新的工程化流水线
                pipeline_output = self.pipeline.run_one_subchapter_new(pipeline_input)
                
                # 检查pipeline_output
                if not hasattr(pipeline_output, 'store_stats') or not pipeline_output.store_stats:
                    logger.error(f"Pipeline未返回存储统计信息: {type(pipeline_output)}")
                    continue
                
                # 收集存储统计信息
                store_stats = pipeline_output.store_stats
                if store_stats.get("success"):
                    nodes_count = store_stats.get("nodes_created", 0) + store_stats.get("nodes_updated", 0)
                    edges_count = store_stats.get("edges_created", 0) + store_stats.get("edges_updated", 0)
                    total_nodes_processed += nodes_count
                    total_edges_processed += edges_count
                    all_section_ids.append(pipeline_output.section_id)
                    
                    logger.info(f"子章节 {current_subchapter_title} 处理完成: {nodes_count} 节点, {edges_count} 边")
                else:
                    logger.warning(f"子章节 {current_subchapter_title} 存储失败: {store_stats.get('error', '未知错误')}")
            
            # 生成book_id并进行书籍级别合并 
            # 使用固定的run_id以确保同一主题的book_id一致
            book_id = generate_book_id(topic, f"{topic}_{language}")
            
            if len(content) > 1 and all_section_ids:
                logger.info(f"执行书籍级别合并: {book_id}")
                
                # 使用新的合并器进行整书级合并
                section_kgs = [(section_id, {"nodes": [], "edges": []}) for section_id in all_section_ids]
                book_context = {
                    "book_id": book_id,
                    "topic": topic,
                    "language": language
                }
                
                try:
                    merged_result = self.pipeline.merge_book_kg(section_kgs, book_context)
                    if merged_result.get("success"):
                        logger.info(f"书籍合并完成: book_id={book_id}")
                    else:
                        logger.warning(f"书籍合并失败: {merged_result.get('error', '未知错误')}")
                except Exception as e:
                    logger.error(f"书籍合并异常: {e}")
            
            return {
                "nodes": [],  # 新流水线不返回具体数据，依赖Neo4j存储
                "edges": [],  # 新流水线不返回具体数据，依赖Neo4j存储
                "hierarchy": f"主题: {topic} | 章节: {chapter_title or '未知'} | 语言: {language}",
                "total_nodes": total_nodes_processed,
                "total_edges": total_edges_processed,
                "section_ids": all_section_ids,
                "book_id": book_id,
                "raw_content": f"工程化流水线处理 {len(content)} 个子章节，存储 {total_nodes_processed} 节点，{total_edges_processed} 边"
            }
            
        except Exception as e:
            logger.error(f"构建知识图谱时出错: {e}")
            raise
    

    def execute(self, state: TextbookState) -> TextbookState:
        """
        执行KG构建 - Agent接口
        
        Args:
            state: 教材状态
            
        Returns:
            更新后的教材状态
        """
        topic = state.get("topic")
        if not topic:
            raise RuntimeError("缺少必需字段: topic")
            
        content = state.get("content", {})
        keywords = state.get("keywords", [])
        language = state.get("language", "中文")
        chapter_title = state.get("chapter_title")
        
        # 如果内容只有一个子章节，提取其标题
        subchapter_title = None
        if len(content) == 1:
            subchapter_title = list(content.keys())[0]
            
        logger.info(f"KGBuilder 开始执行，主题: {topic}")
        logger.info(f"内容包含 {len(content)} 个子章节")
        
        # 使用新的工程化流水线构建KG
        kg_result = self.build_knowledge_graph(
            topic=topic,
            content=content,
            keywords=keywords,
            language=language,
            chapter_title=chapter_title,
            subchapter_title=subchapter_title
        )
        
        # 更新状态
        state["kg"] = {
            "nodes": kg_result["nodes"],
            "edges": kg_result["edges"],
            "hierarchy": kg_result["hierarchy"]
        }
        state["kg_content"] = kg_result["raw_content"]
        state["kg_complete"] = True
        state["kg_section_ids"] = kg_result.get("section_ids", [])
        state["book_id"] = kg_result.get("book_id")
        
        logger.info(f"KGBuilder 完成，节点数: {kg_result.get('total_nodes', 0)}, 边数: {kg_result.get('total_edges', 0)}")
        logger.info(f"生成的章节ID: {kg_result.get('section_ids', [])}")
        logger.info(f"生成的book_id: {kg_result.get('book_id')}")
        
        return state


__all__ = ["KGBuilder"]