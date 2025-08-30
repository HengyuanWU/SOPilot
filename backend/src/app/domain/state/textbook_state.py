#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing_extensions import TypedDict
from typing import Dict, List, Any, Optional


class TextbookState(TypedDict, total=False):
    topic: str
    language: str
    num_chapters: int
    chapter_count: int
    thread_id: Optional[str]

    outline: Optional[str]
    chapters: Optional[List[Dict[str, Any]]]

    research_content: Optional[Dict[str, str]]
    subchapter_keywords_map: Optional[Dict[str, List[str]]]
    chapter_keywords_map: Optional[Dict[str, List[str]]]
    global_unique_keywords: Optional[List[str]]

    content: Optional[Dict[str, str]]
    validation_results: Optional[Dict[str, Dict[str, Any]]]

    qa_results: Optional[Dict[str, Dict[str, Any]]]
    qa_content: Optional[Dict[str, str]]
    qa_metadata: Optional[Dict[str, Any]]

    knowledge_graphs: Optional[Dict[str, Dict[str, Any]]]
    merged_knowledge_graph: Optional[Dict[str, Any]]

    cross_agent_insights: Optional[Dict[str, Dict[str, Any]]]

    final_content: Optional[str]

    # KG 相关：保证在状态图中不被丢弃
    section_ids: Optional[List[str]]
    section_id: Optional[str]

    # 新增：整本书图谱信息
    book_id: Optional[str]
    book_store_stats: Optional[Dict[str, Any]]

    kg_store_stats: Optional[Dict[str, Any]]
    processing_stats: Optional[Dict[str, Any]]

    config: Optional[Dict[str, Any]]
    error: Optional[str]

