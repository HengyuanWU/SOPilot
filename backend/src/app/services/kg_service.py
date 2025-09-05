from __future__ import annotations

from typing import Any, Dict, Optional
from ..infrastructure.graph_store.neo4j_store import fetch_section_graph, fetch_book_graph, create_neo4j_store
import logging

logger = logging.getLogger(__name__)


def get_section(section_id: str) -> Optional[Dict[str, Any]]:
    """
    获取指定 section 的 KG 片段，但统一使用 Book Scope 查询。
    
    根据 IMPROVE_GUIDE.md 第4.4节，统一使用 Book Scope，
    自动查找 section_id 对应的 book_id 并返回整书数据。
    """
    if not section_id:
        return None
    
    # 查找 section_id 对应的 book_id
    book_id = _find_book_id_by_section(section_id)
    if not book_id:
        # 如果找不到对应的 book，返回空结果但保持接口兼容
        return {
            "section_id": section_id,
            "nodes": [],
            "edges": [],
            "stats": {"total_nodes": 0, "total_edges": 0}
        }
    
    # 使用 book scope 查询，但返回 section 格式保持前端兼容
    book_data = fetch_book_graph(book_id)
    if not book_data:
        return {
            "section_id": section_id,
            "nodes": [],
            "edges": [],
            "stats": {"total_nodes": 0, "total_edges": 0}
        }
    
    # 转换为 section 格式以保持前端兼容
    return {
        "section_id": section_id,
        "nodes": book_data.get("nodes", []),
        "edges": book_data.get("edges", []),
        "stats": book_data.get("stats", {"total_nodes": 0, "total_edges": 0}),
        "book_id": book_id  # 额外提供 book_id 给前端
    }


def get_book(book_id: str) -> Optional[Dict[str, Any]]:
    """获取整本书的 KG 视图（若未配置 Neo4j，则返回 None）。"""
    if not book_id:
        return None
    return fetch_book_graph(book_id)


def _find_book_id_by_section(section_id: str) -> Optional[str]:
    """
    通过 section_id 查找对应的 book_id。
    
    统一 Book Scope 架构下，所有 KG 数据都存储在 book scope 中，
    需要通过查询找到 section_id 对应的 book_id。
    
    Args:
        section_id: 子章节ID
        
    Returns:
        对应的 book_id，如果找不到则返回 None
    """
    try:
        store = create_neo4j_store()
        if not store:
            logger.warning("Neo4j store not available")
            return None
        
        # 查询所有包含此 section_id 的边，获取其 scope
        query = """
        MATCH ()-[r]->() 
        WHERE r.src_section = $section_id 
        RETURN DISTINCT r.scope AS scope
        LIMIT 1
        """
        
        result = store.client.execute_cypher(query, {"section_id": section_id})
        if result and len(result) > 0:
            scope = result[0].get("scope")
            if scope and scope.startswith("book:"):
                # 移除 "book:" 前缀，返回纯净的 book_id
                return scope[5:]  # 去掉 "book:" 前缀
            return scope
        
        logger.debug(f"No book found for section_id: {section_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error finding book_id for section {section_id}: {e}")
        return None

