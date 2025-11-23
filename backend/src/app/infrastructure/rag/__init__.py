#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG (Retrieval-Augmented Generation) 基础设施 - LangChain 实现

基于 LangChain 标准组件的 RAG 系统：
- LangChain Embeddings (SiliconFlowEmbeddings)
- LangChain Vector Store (LangChainQdrantStore)  
- LangChain Retrievers (HybridRetriever)
- LangChain Text Splitters
- Neo4j KG 检索集成
"""

from .pipeline import RAGPipeline, RAGConfig, RAGRetrievalResult
from .chunker import DocumentChunker, DocumentChunk
from .embeddings import SiliconFlowEmbeddings, create_cached_embeddings
from .vectorstore import LangChainQdrantStore, VectorStoreConfig
from .retriever_factory import create_ensemble_retriever, documents_to_dict
from .text_splitter import get_text_splitter, split_text_by_type

# 保留旧的导入以兼容现有代码
from .merger import EvidenceMerger, MergedEvidence
from .prompt_builder import PromptBuilder, PromptContext

__all__ = [
    # 核心组件
    "RAGPipeline",
    "RAGConfig",
    "RAGRetrievalResult",
    "DocumentChunker", 
    "DocumentChunk",
    
    # LangChain 组件
    "SiliconFlowEmbeddings",
    "create_cached_embeddings",
    "LangChainQdrantStore",
    "VectorStoreConfig",
    "create_ensemble_retriever",
    "documents_to_dict",
    "get_text_splitter",
    "split_text_by_type",
    
    # 旧组件（仍在使用）
    "EvidenceMerger",
    "MergedEvidence",
    "PromptBuilder",
    "PromptContext",
]