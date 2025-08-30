#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict


class NodeDict(TypedDict):
    id: str
    type: str
    name: str
    description: Optional[str]
    canonical_key: Optional[str]
    aliases: List[str]
    chapter: Optional[str]
    subchapter: Optional[str]
    score: Optional[float]
    source: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class EdgeDict(TypedDict):
    id: str
    type: str
    source_id: str
    target_id: str
    source_name: Optional[str]
    target_name: Optional[str]
    weight: Optional[float]
    confidence: Optional[float]
    evidence: Optional[str]
    chapter: Optional[str]
    src: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class KGDict(TypedDict):
    nodes: List[NodeDict]
    edges: List[EdgeDict]
    hierarchy: Optional[str]
    total_nodes: Optional[int]
    total_edges: Optional[int]
    chapters_covered: Optional[List[str]]


@dataclass
class KGPipelineInput:
    topic: str
    chapter_title: str
    subchapter_title: str
    content: str
    keywords: List[str]
    language: str = "中文"


@dataclass
class KGPipelineOutput:
    section_id: str
    content_hash: str
    kg_part: KGDict
    insights: Dict[str, Any]
    store_stats: Dict[str, Any]


class KGInsights(TypedDict):
    kg_structure: Dict[str, Any]
    node_relationships: Dict[str, Any]
    knowledge_coverage: Dict[str, Any]
    kg_summary: str

