from __future__ import annotations

from typing import Any, Dict, Optional
from ..infrastructure.graph_store.neo4j_store import fetch_section_graph, fetch_book_graph


def get_section(section_id: str) -> Optional[Dict[str, Any]]:
    """获取指定 section 的 KG 片段（若未配置 Neo4j，则返回 None）。"""
    if not section_id:
        return None
    return fetch_section_graph(section_id)


def get_book(book_id: str) -> Optional[Dict[str, Any]]:
    """获取整本书的 KG 视图（若未配置 Neo4j，则返回 None）。"""
    if not book_id:
        return None
    return fetch_book_graph(book_id)

