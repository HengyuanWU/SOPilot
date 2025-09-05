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
            
        # 工程化流水线架构：直接从状态获取book_id，不依赖内存中的merged_kg
        book_id = state.get("book_id")
        if not book_id:
            # 如果kg_builder没有设置book_id，生成一个fallback
            book_id = generate_book_id(topic, thread_id)
            logger.warning(f"kg_builder未设置book_id，生成fallback: {book_id}")
        else:
            logger.info(f"使用kg_builder设置的book_id: {book_id}")
            # 重要：不要重新生成，直接使用kg_builder的book_id
            
        # 检查是否有KG数据被存储（通过section_ids判断）
        section_ids = state.get("section_ids", [])
        if not section_ids:
            logger.warning("没有KG section_ids，跳过整本书图谱持久化")
            # 但仍然设置book_id到状态中
            result_state = state.copy()
            result_state["book_id"] = book_id
            return result_state
        
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
            
            # 新策略：从Neo4j中读取section数据并重新标记为book_scope
            logger.info(f"开始从Neo4j读取section数据并重新标记为book_scope")
            
            # 获取所有section的边数据 - 使用直接的Neo4j客户端
            section_edges = []
            
            # 创建独立的Neo4j客户端进行查询
            from app.infrastructure.graph_store.neo4j_client import create_neo4j_client
            from app.core.settings import get_settings
            
            settings = get_settings()
            neo4j_config = {
                "neo4j": {
                    "uri": settings.neo4j.uri,
                    "user": settings.neo4j.user,
                    "password": settings.neo4j.password,
                    "database": settings.neo4j.database
                }
            }
            
            query_client = create_neo4j_client(neo4j_config)
            if not query_client:
                logger.error("无法创建Neo4j查询客户端")
                edges_written = 0
            else:
                for section_id in section_ids:
                    try:
                        # 查询该section的所有边，直接获取属性
                        section_scope = f"section:{section_id}"
                        
                        result = query_client.execute_cypher(
                            """
                            MATCH ()-[r]->() WHERE r.scope = $scope 
                            RETURN r.type as type, r.source_id as source_id, r.target_id as target_id, 
                                   r.confidence as confidence, r.weight as weight, r.desc as desc,
                                   r.rid as old_rid, r.scope as old_scope
                            """,
                            {"scope": section_scope}
                        )
                        section_edges.extend(result)
                        logger.info(f"从section {section_id} 读取到 {len(result)} 条边")
                    except Exception as e:
                        logger.error(f"读取section {section_id} 数据失败: {e}")
                
                logger.info(f"总共读取到 {len(section_edges)} 条section边数据")
                
                # 节点在各个section中已经存储，不需要重复写入
                nodes_written = 0
                
                # 为每条边重新创建book_scope版本
                edges_written = 0
                from app.domain.kg.ids import generate_relation_rid
            
                for edge_data in section_edges:
                    try:
                        # edge_data是字典，包含从Cypher查询返回的字段
                        # 创建新的book_scope边
                        edge_copy = {
                            "type": edge_data.get("type", ""),
                            "source_id": edge_data.get("source_id", ""),
                            "target_id": edge_data.get("target_id", ""),
                            "desc": edge_data.get("desc", ""),
                            "confidence": edge_data.get("confidence", 0.8),
                            "weight": edge_data.get("weight", 1.0),
                            "scope": book_scope,  # 新的book scope
                            # 不设置src，因为这是整书级别的关系
                        }
                        
                        # 生成新的rid
                        edge_copy["rid"] = generate_relation_rid(
                            edge_copy["type"], 
                            edge_copy["source_id"], 
                            edge_copy["target_id"], 
                            book_scope
                        )
                        
                        if store.merge_edge(edge_copy):
                            edges_written += 1
                    except Exception as e:
                        logger.error(f"处理边数据失败: {e}")
                        continue
                    
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