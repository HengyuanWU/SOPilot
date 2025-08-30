#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整本书图谱持久化节点

职责：
- 获取合并后的知识图谱
- 生成book_id
- 将整本书图谱以book scope存储到Neo4j
- 提供整本书视图的统计信息
"""

import logging
from typing import Dict, Any

from app.domain.kg.ids import generate_book_id, generate_relation_rid
from app.domain.kg.store import KGStore

logger = logging.getLogger(__name__)


def book_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    整本书图谱持久化节点处理函数
    
    输入状态字段:
    - topic: 教材主题
    - thread_id: 工作流线程ID
    - merged_knowledge_graph: 合并后的知识图谱
    
    输出状态字段:
    - book_id: 整本书ID
    - book_store_stats: 存储统计信息
    """
    try:
        if state.get("error"):
            return state
            
        logger.info("开始执行整本书图谱持久化节点")
        
        # 获取必要的状态信息
        topic = state.get("topic")
        thread_id = state.get("thread_id")
        merged_kg = state.get("merged_knowledge_graph", {})
        
        if not topic:
            logger.warning("缺少topic，跳过整本书图谱持久化")
            return state
            
        if not thread_id:
            logger.warning("缺少thread_id，跳过整本书图谱持久化")
            return state
            
        if not merged_kg or not merged_kg.get("edges"):
            logger.warning("缺少合并后的知识图谱或图谱为空，跳过整本书图谱持久化")
            return state
        
        # 生成book_id
        book_id = generate_book_id(topic, thread_id)
        logger.info(f"生成book_id: {book_id}")
        
        # 初始化存储
        try:
            from app.infrastructure.graph_store import create_neo4j_store
            store = create_neo4j_store()
            if not store:
                logger.warning("Neo4j存储未可用，跳过整本书图谱持久化")
                return state
        except Exception as e:
            logger.error(f"初始化Neo4j存储失败: {e}")
            return state
        
        # 存储统计
        book_stats = {
            "attempted": True,
            "success": False,
            "nodes_written": 0,
            "edges_written": 0,
            "edges_deleted": 0,
            "error": None
        }
        
        try:
            # 整本书scope - book_id已经包含"book:"前缀
            book_scope = book_id
            
            # 清理旧的整本书关系
            edges_deleted = store.delete_edges_by_scope(book_scope)
            book_stats["edges_deleted"] = edges_deleted
            logger.info(f"清理旧整本书关系: {edges_deleted} 条")
            
            # 写入节点（节点是共享的，不需要scope区分）
            nodes_written = 0
            for node in merged_kg.get("nodes", []):
                if store.merge_node(node):
                    nodes_written += 1
            book_stats["nodes_written"] = nodes_written
            
            # 写入整本书关系，添加scope和rid
            edges_written = 0
            for edge in merged_kg.get("edges", []):
                edge_copy = edge.copy()
                edge_copy["scope"] = book_scope
                # 注意：整本书关系不设置src，与小节视图区分
                
                # 生成rid
                edge_type = edge_copy.get("type", "")
                source_id = edge_copy.get("source_id", "")
                target_id = edge_copy.get("target_id", "")
                edge_copy["rid"] = generate_relation_rid(edge_type, source_id, target_id, book_scope)
                
                if store.merge_edge(edge_copy):
                    edges_written += 1
                    
            book_stats["edges_written"] = edges_written
            book_stats["success"] = True
            
            logger.info(f"整本书图谱存储完成: {nodes_written} 节点, {edges_written} 边")
            
        except Exception as e:
            book_stats["error"] = str(e)
            book_stats["success"] = False
            logger.error(f"整本书图谱存储失败: {e}")
        
        # 更新状态
        result_state = state.copy()
        result_state["book_id"] = book_id
        result_state["book_store_stats"] = book_stats
        
        # 更新处理统计
        try:
            stats = result_state.get("processing_stats", {}) or {}
            stats["book_graph"] = {
                "book_id": book_id,
                "nodes_written": book_stats["nodes_written"],
                "edges_written": book_stats["edges_written"],
                "success": book_stats["success"]
            }
            result_state["processing_stats"] = stats
        except Exception:
            pass
            
        logger.info("整本书图谱持久化节点执行完成")
        return result_state
        
    except Exception as e:
        logger.error(f"整本书图谱节点执行失败: {e}")
        error_state = state.copy()
        error_state["error"] = f"整本书图谱持久化失败: {str(e)}"
        return error_state


__all__ = ["book_graph_node"]