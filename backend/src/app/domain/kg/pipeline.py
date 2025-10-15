#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端流水线（按IMPROOVE_GUIDE.md规范）
唯一入口：KGPipeline.run(section) -> result
禁止旁路调用
"""

from __future__ import annotations

import logging
import hashlib
from typing import TYPE_CHECKING

from .builder import KGBuilder
from .idempotent import IdGen
from .linker import EntityLinker
from .merger import BookMerger
from .normalizer import KGNormalizer
from .store import KGStore
from .ids import generate_section_id

if TYPE_CHECKING:
    from .schemas import KGPipelineInput, KGPipelineOutput

__all__ = ["KGPipeline"]

logger = logging.getLogger(__name__)


class KGPipeline:
    """知识图谱端到端流水线。"""

    def __init__(self, settings):
        """初始化流水线。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings
        self.builder = KGBuilder(settings)
        self.normalizer = KGNormalizer(settings)
        self.linker = EntityLinker(settings)
        self.idgen = IdGen(settings)
        self.store = KGStore(settings)
        self.merger = BookMerger(settings)

    def run_one_subchapter(self, pipeline_input: "KGPipelineInput") -> "KGPipelineOutput":
        """
        运行单个小节的KG构建流水线（适配层方法）
        
        Args:
            pipeline_input: 流水线输入数据
            
        Returns:
            KGPipelineOutput: 包含section_id、kg_part、insights和store_stats
        """
        from .schemas import KGPipelineOutput, KGDict
        from .evaluator import KGEvaluator
        
        try:
            # 1. 生成section_id
            section_id = generate_section_id(
                pipeline_input.topic,
                pipeline_input.chapter_title,
                pipeline_input.subchapter_title
            )
            
            # 2. 计算内容哈希
            content_hash = hashlib.md5(pipeline_input.content.encode('utf-8')).hexdigest()
            
            # 3. 构建section字典用于run方法
            section = {
                'section_id': section_id,
                'book_topic': pipeline_input.topic,
                'chapter_title': pipeline_input.chapter_title,
                'subchapter_title': pipeline_input.subchapter_title,
                'chunks': [
                    {
                        'id': f'{section_id}#chunk_0',
                        'text': pipeline_input.content
                    }
                ]
            }
            
            # 4. 运行新的工程化流水线
            logger.info(f"开始处理小节: {section_id}")
            result = self.run(section)
            
            # 5. 构建返回的kg_part（用于兼容性）
            # 注意：新流水线不返回详细节点/边数据，只返回统计
            stats = result.get('stats', {})
            kg_part = {
                'nodes': [],  # 新流水线数据存储在Neo4j中
                'edges': [],  # 新流水线数据存储在Neo4j中
                'hierarchy': f"{pipeline_input.chapter_title} > {pipeline_input.subchapter_title}",
                'total_nodes': stats.get('nodes', 0),
                'total_edges': stats.get('edges', 0),
                'chapters_covered': [pipeline_input.chapter_title]
            }
            
            # 6. 生成insights（评估指标）
            evaluator = KGEvaluator()
            insights = {
                'kg_structure': {
                    'total_nodes': stats.get('nodes', 0),
                    'total_edges': stats.get('edges', 0),
                    'avg_degree': stats.get('edges', 0) / max(stats.get('nodes', 1), 1)
                },
                'node_relationships': {
                    'relationship_types': {},
                    'relation_richness': 0.0
                },
                'knowledge_coverage': {
                    'covered_keywords': pipeline_input.keywords,
                    'coverage_score': 1.0 if stats.get('nodes', 0) > 0 else 0.0
                }
            }
            
            # 7. 构建store_stats
            store_stats = {
                'success': stats.get('nodes', 0) > 0 or stats.get('edges', 0) > 0,
                'section_id': section_id,
                'nodes_created': stats.get('nodes', 0),
                'nodes_updated': 0,
                'edges_created': stats.get('edges', 0),
                'edges_updated': 0,
                'edges_deleted': 0,
                'nodes_written': stats.get('nodes', 0),
                'edges_written': stats.get('edges', 0)
            }
            
            logger.info(f"小节 {section_id} 处理完成: {stats}")
            
            return KGPipelineOutput(
                section_id=section_id,
                content_hash=content_hash,
                kg_part=kg_part,
                insights=insights,
                store_stats=store_stats
            )
            
        except Exception as e:
            logger.error(f"处理小节失败: {e}", exc_info=True)
            # 返回失败的输出
            from .schemas import KGPipelineOutput
            section_id = generate_section_id(
                pipeline_input.topic,
                pipeline_input.chapter_title,
                pipeline_input.subchapter_title
            )
            content_hash = hashlib.md5(pipeline_input.content.encode('utf-8')).hexdigest()
            
            return KGPipelineOutput(
                section_id=section_id,
                content_hash=content_hash,
                kg_part={
                    'nodes': [],
                    'edges': [],
                    'hierarchy': '',
                    'total_nodes': 0,
                    'total_edges': 0,
                    'chapters_covered': []
                },
                insights={
                    'kg_structure': {'total_nodes': 0, 'total_edges': 0},
                    'node_relationships': {},
                    'knowledge_coverage': {'coverage_score': 0.0}
                },
                store_stats={
                    'success': False,
                    'error': str(e),
                    'nodes_written': 0,
                    'edges_written': 0
                }
            )

    def run(self, section: dict) -> dict:
        """执行完整的KG构建流水线。
        
        Args:
            section: 小节数据，格式：
                {
                    'section_id': 'sec_xxx',
                    'book_topic': '大型语言模型',
                    'chapter_title': 'RAG 基础',
                    'subchapter_title': '向量检索',
                    'chunks': [
                        {'id': 'doc1#p3', 'text': '...'},
                        ...
                    ]
                }
                
        Returns:
            结果字典：
                {
                    'section_id': 'sec_xxx',
                    'book_id': None,  # book_id由外层book_graph_node统一生成
                    'stats': {'nodes': N, 'edges': M}
                }
        """
        # 1) 抽取（NER/RE）
        draft = self.builder.extract(section)
        
        # 2) 规范化
        draft = self.normalizer.normalize(draft)
        
        # 3) 实体链接（对齐既有图谱）
        linked = self.linker.link(draft)
        
        # 4) 生成 ID/RID
        ready = self.idgen.assign(linked, section)
        
        # 5) 小节级入库（Section Scope）
        self.store.write_section(ready, section["section_id"])
        
        # 6) ✅ 修复：移除每个section都调用merge_book的问题
        # 书籍级别合并由外层的book_graph_node统一负责，避免重复写入
        # 详见：backend/src/app/domain/workflows/textbook/nodes/book_graph_node.py
        
        return {
            "section_id": section["section_id"],
            "book_id": None,  # 由book_graph_node统一生成
            "stats": self.store.stats,
        }
