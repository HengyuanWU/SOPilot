#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG (Retrieval-Augmented Generation) 基础设施

按照 IMPROOVE_GUIDE.md 的双通道并行检索架构：
- Qdrant 向量检索（语义召回）
- Neo4j KG 检索（结构关系）
- Merger/Rerank → Prompt 构造 → LLM
"""

from .pipeline import RAGPipeline, RAGConfig
from .chunker import DocumentChunker, DocumentChunk
from .embedder import Embedder, EmbeddingResult
from .merger import EvidenceMerger, MergedEvidence
from .prompt_builder import PromptBuilder, PromptContext

__all__ = [
    "RAGPipeline",
    "RAGConfig",
    "DocumentChunker", 
    "DocumentChunk",
    "Embedder",
    "EmbeddingResult",
    "EvidenceMerger",
    "MergedEvidence",
    "PromptBuilder",
    "PromptContext",
]