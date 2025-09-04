#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict
from datetime import datetime


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


# 新的工程化KG数据结构
@dataclass
class KGNode:
    """知识图谱节点"""
    id: str
    name: str
    type: str
    desc: str = ""
    aliases: List[str] = None
    scope: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


@dataclass
class KGEdge:
    """知识图谱边"""
    rid: str
    type: str
    source: str
    target: str
    desc: str = ""
    confidence: float = 0.8
    weight: float = 1.0
    scope: str = ""
    src_section: str = ""
    created_at: Optional[datetime] = None


@dataclass
class KGDict:
    """知识图谱数据容器"""
    nodes: List[KGNode]
    edges: List[KGEdge]
    hierarchy: str = ""
    total_nodes: int = 0
    total_edges: int = 0
    chapters_covered: List[str] = None
    
    def __post_init__(self):
        if self.chapters_covered is None:
            self.chapters_covered = []
        if self.total_nodes == 0:
            self.total_nodes = len(self.nodes)
        if self.total_edges == 0:
            self.total_edges = len(self.edges)

