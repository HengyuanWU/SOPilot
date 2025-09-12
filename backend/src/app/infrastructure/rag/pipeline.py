#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Pipeline - RAG系统统一管线

按照IMPROOVE_GUIDE.md的双通道并行检索架构：
- Qdrant向量检索（语义召回）+ Neo4j KG检索（结构关系）
- Merger/Rerank → Prompt构造 → LLM

统一对外接口：ingest / index / retrieve / test
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
from dataclasses import dataclass
import asyncio

from .chunker import DocumentChunker, DocumentChunk
from .embedder import Embedder
from .vectorstores.qdrant_store import QdrantStore
from .kgstores.neo4j_queries import Neo4jKGQueries
from .kgstores.document_store import DocumentKGStore
from .nlp.entity_extractor import EntityExtractor
from .retrievers.retriever_vector import VectorRetriever
from .retrievers.retriever_kg import KGRetriever
from .merger import EvidenceMerger, MergedEvidence
from .rerankers.bge_reranker import BGEReranker
from .prompt_builder import PromptBuilder, PromptContext

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """RAG配置"""
    # 基础配置
    base_dir: str = "knowledge_base"
    
    # 文档分块配置
    chunk_size: int = 800
    chunk_overlap: int = 120
    
    # 嵌入配置（基于API调用）
    embed_model: str = "BAAI/bge-small-zh-v1.5"
    embed_provider: str = "siliconflow"  # 嵌入模型提供商
    
    # Qdrant配置
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "kb_chunks"
    qdrant_distance: str = "cosine"
    
    # 检索配置
    vector_top_k: int = 12
    kg_top_k: int = 8
    final_top_k: int = 4
    
    # 合并配置
    alpha: float = 0.7  # 向量权重
    beta: float = 0.3   # KG权重
    
    # 重排配置
    use_reranker: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    
    # KG检索配置
    kg_hop: int = 2
    kg_rel_types: List[str] = None
    
    # 提示构造配置
    max_context_length: int = 4000
    citation_style: str = "numbered"


@dataclass
class RAGRetrievalResult:
    """RAG检索结果"""
    query: str
    vector_hits: List[Dict[str, Any]]
    kg_hits: List[Dict[str, Any]]
    merged_evidence: List[MergedEvidence]
    enhanced_prompt: Optional[PromptContext] = None
    metadata: Dict[str, Any] = None


class RAGPipeline:
    """RAG系统主管线"""
    
    def __init__(self, config: RAGConfig = None):
        """
        初始化RAG管线
        
        Args:
            config: RAG配置
        """
        self.config = config or RAGConfig()
        self.logger = logging.getLogger(__name__)
        
        # 初始化各个组件
        self._init_components()
    
    def _init_components(self):
        """初始化各个组件"""
        try:
            # 文档处理组件
            self.chunker = DocumentChunker(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap
            )
            
            self.embedder = Embedder(
                model_name=self.config.embed_model,
                provider=self.config.embed_provider
            )
            
            # 存储组件
            self.qdrant_store = QdrantStore(
                url=self.config.qdrant_url,
                collection_name=self.config.qdrant_collection
            )
            
            self.neo4j_queries = Neo4jKGQueries()
            self.document_store = DocumentKGStore(self.neo4j_queries._client)
            self.entity_extractor = EntityExtractor()
            
            # 检索组件
            self.vector_retriever = VectorRetriever(
                qdrant_store=self.qdrant_store,
                embedder=self.embedder
            )
            
            self.kg_retriever = KGRetriever(
                neo4j_queries=self.neo4j_queries
            )
            
            # 合并和重排组件
            self.evidence_merger = EvidenceMerger(
                alpha=self.config.alpha,
                beta=self.config.beta
            )
            
            self.reranker = BGEReranker(
                model_name=self.config.reranker_model,
                enabled=self.config.use_reranker
            )
            
            # 提示构造组件
            self.prompt_builder = PromptBuilder(
                max_context_length=self.config.max_context_length,
                citation_style=self.config.citation_style
            )
            
            self.logger.info("RAG管线组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"RAG管线初始化失败: {e}")
            raise
    
    def ingest_documents(self, file_paths: List[Union[str, Path]], 
                        doc_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        文档入库
        
        Args:
            file_paths: 文档文件路径列表
            doc_metadata: 文档元数据
            
        Returns:
            Dict[str, Any]: 入库结果统计
        """
        try:
            self.logger.info(f"开始文档入库: {len(file_paths)} 个文件")
            
            all_chunks = []
            processing_stats = {
                "total_files": len(file_paths),
                "processed_files": 0,
                "total_chunks": 0,
                "failed_files": [],
            }
            
            # 1. 文档分块
            for file_path in file_paths:
                try:
                    file_path = Path(file_path)
                    doc_id = file_path.stem
                    
                    # 合并元数据
                    meta = doc_metadata.copy() if doc_metadata else {}
                    meta.update({
                        "filename": file_path.name,
                        "file_path": str(file_path),
                    })
                    
                    # 分块
                    chunks = self.chunker.chunk_file(file_path, doc_id, meta)
                    all_chunks.extend(chunks)
                    
                    processing_stats["processed_files"] += 1
                    self.logger.debug(f"文件分块完成: {file_path.name}, {len(chunks)} 个块")
                    
                except Exception as e:
                    self.logger.error(f"文件处理失败 {file_path}: {e}")
                    processing_stats["failed_files"].append(str(file_path))
            
            processing_stats["total_chunks"] = len(all_chunks)
            
            # 2. 保存分块结果
            chunks_file = Path(self.config.base_dir) / "chunks" / "latest_chunks.jsonl"
            self.chunker.save_chunks_to_jsonl(all_chunks, chunks_file)
            
            self.logger.info(f"文档入库完成: 处理 {processing_stats['processed_files']} 个文件，生成 {len(all_chunks)} 个分块")
            return processing_stats
            
        except Exception as e:
            self.logger.error(f"文档入库失败: {e}")
            raise
    
    def index_documents(self, chunk_file: Union[str, Path] = None, 
                       force_recreate: bool = False) -> Dict[str, Any]:
        """
        文档索引
        
        Args:
            chunk_file: 分块文件路径（如果为None，使用最新的分块文件）
            force_recreate: 是否强制重新创建集合
            
        Returns:
            Dict[str, Any]: 索引结果统计
        """
        try:
            # 确定分块文件
            if chunk_file is None:
                chunk_file = Path(self.config.base_dir) / "chunks" / "latest_chunks.jsonl"
            
            chunk_file = Path(chunk_file)
            if not chunk_file.exists():
                raise FileNotFoundError(f"分块文件不存在: {chunk_file}")
            
            self.logger.info(f"开始文档索引: {chunk_file}")
            
            # 1. 读取分块数据
            chunks_data = self._load_chunks_from_jsonl(chunk_file)
            
            # 2. 生成向量
            self.logger.info(f"开始向量化 {len(chunks_data)} 个文档块")
            texts = [chunk["text"] for chunk in chunks_data]
            embedding_results = self.embedder.embed_batch(texts)
            
            # 3. 准备Qdrant数据
            documents_for_qdrant = []
            for chunk_data, embedding in zip(chunks_data, embedding_results):
                doc = dict(chunk_data)
                doc["vector"] = embedding.vector.tolist()
                doc["embedding_model"] = embedding.model_name
                doc["vector_dimension"] = embedding.dimension
                documents_for_qdrant.append(doc)
            
            # 4. 创建/更新Qdrant集合
            vector_dim = embedding_results[0].dimension if embedding_results else 384
            collection_created = self.qdrant_store.create_collection(
                vector_size=vector_dim,
                distance=self.config.qdrant_distance,
                force_recreate=force_recreate
            )
            
            if not collection_created:
                raise RuntimeError("Qdrant集合创建失败")
            
            # 5. 批量插入向量
            upsert_success = self.qdrant_store.upsert_vectors(documents_for_qdrant)
            
            if not upsert_success:
                raise RuntimeError("向量数据插入失败")
            
            # 6. 统计信息
            collection_info = self.qdrant_store.get_collection_info()
            
            index_stats = {
                "indexed_chunks": len(chunks_data),
                "vector_dimension": vector_dim,
                "collection_info": collection_info,
                "embedding_model": self.config.embed_model,
                "force_recreate": force_recreate,
            }
            
            self.logger.info(f"文档索引完成: {len(chunks_data)} 个文档块")
            return index_stats
            
        except Exception as e:
            self.logger.error(f"文档索引失败: {e}")
            raise
    
    def retrieve(self, query: str, top_k: int = None, include_kg: bool = True, 
                scope: str = None) -> RAGRetrievalResult:
        """
        双通道检索
        
        Args:
            query: 查询文本
            top_k: 最终返回结果数量
            include_kg: 是否包含KG检索
            scope: 检索范围（如book_id）
            
        Returns:
            RAGRetrievalResult: 检索结果
        """
        try:
            top_k = top_k or self.config.final_top_k
            self.logger.debug(f"开始双通道检索: query='{query[:50]}...', top_k={top_k}")
            
            # 1. 向量检索
            vector_results = self.vector_retriever.search(
                query=query,
                top_k=self.config.vector_top_k
            )
            
            # 2. KG检索（如果启用）
            kg_results = []
            if include_kg:
                kg_results = self.kg_retriever.search(
                    query=query,
                    top_k=self.config.kg_top_k,
                    hop=self.config.kg_hop,
                    rel_types=self.config.kg_rel_types,
                    scope=scope
                )
            
            # 3. 合并证据
            merged_evidence = self.evidence_merger.merge(
                vector_results=vector_results,
                kg_results=kg_results,
                max_results=top_k * 2  # 为重排预留更多候选
            )
            
            # 4. 重排（如果启用）
            if self.config.use_reranker and merged_evidence:
                reranked_results = self.reranker.rerank(
                    query=query,
                    evidence_list=merged_evidence,
                    top_k=top_k
                )
                final_evidence = [r.evidence for r in reranked_results]
            else:
                final_evidence = merged_evidence[:top_k]
            
            # 5. 构建结果
            result = RAGRetrievalResult(
                query=query,
                vector_hits=self._format_vector_hits(vector_results),
                kg_hits=self._format_kg_hits(kg_results),
                merged_evidence=final_evidence,
                metadata={
                    "vector_count": len(vector_results),
                    "kg_count": len(kg_results),
                    "merged_count": len(merged_evidence),
                    "final_count": len(final_evidence),
                    "reranker_used": self.config.use_reranker,
                    "config": {
                        "vector_top_k": self.config.vector_top_k,
                        "kg_top_k": self.config.kg_top_k,
                        "alpha": self.config.alpha,
                        "beta": self.config.beta,
                    }
                }
            )
            
            self.logger.info(f"双通道检索完成: vector={len(vector_results)}, kg={len(kg_results)}, final={len(final_evidence)}")
            return result
            
        except Exception as e:
            self.logger.error(f"双通道检索失败: {e}")
            raise
    
    def build_enhanced_prompt(self, base_prompt: str, query: str, 
                            top_k: int = None, include_kg: bool = True) -> PromptContext:
        """
        构建增强的提示
        
        Args:
            base_prompt: 基础提示
            query: 查询（用于检索相关证据）
            top_k: 检索结果数量
            include_kg: 是否包含KG检索
            
        Returns:
            PromptContext: 增强的提示上下文
        """
        try:
            # 1. 检索相关证据
            retrieval_result = self.retrieve(
                query=query,
                top_k=top_k,
                include_kg=include_kg
            )
            
            # 2. 构建增强提示
            enhanced_prompt = self.prompt_builder.build_enhanced_prompt(
                base_prompt=base_prompt,
                evidence=retrieval_result.merged_evidence,
                include_citations=True
            )
            
            # 3. 添加检索元数据
            enhanced_prompt.context_length = len(enhanced_prompt.enhanced_prompt)
            
            return enhanced_prompt
            
        except Exception as e:
            self.logger.error(f"构建增强提示失败: {e}")
            raise
    
    def test_vector_retrieval(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        测试向量检索
        
        Args:
            query: 测试查询
            top_k: 结果数量
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            results = self.vector_retriever.search(query=query, top_k=top_k)
            
            return {
                "query": query,
                "results_count": len(results),
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "doc_id": r.doc_id,
                        "score": r.score,
                        "content_preview": r.text[:200] + "..." if len(r.text) > 200 else r.text,
                        "meta": r.meta,
                    }
                    for r in results
                ],
                "statistics": self.vector_retriever.get_statistics(),
            }
            
        except Exception as e:
            self.logger.error(f"向量检索测试失败: {e}")
            return {"error": str(e)}
    
    def test_kg_retrieval(self, query: str, hop: int = 2, top_k: int = 5) -> Dict[str, Any]:
        """
        测试KG检索
        
        Args:
            query: 测试查询
            hop: 跳数
            top_k: 结果数量
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            results = self.kg_retriever.search(
                query=query,
                top_k=top_k,
                hop=hop,
                rel_types=self.config.kg_rel_types
            )
            
            return {
                "query": query,
                "hop": hop,
                "results_count": len(results),
                "results": [
                    {
                        "type": r.type,
                        "score": r.score,
                        "content": r.content,
                        "explanation": r.explanation,
                        "data": r.data,
                    }
                    for r in results
                ],
                "statistics": self.kg_retriever.get_statistics(),
            }
            
        except Exception as e:
            self.logger.error(f"KG检索测试失败: {e}")
            return {"error": str(e)}
    
    def test_dual_retrieval(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        """
        测试双通道检索
        
        Args:
            query: 测试查询
            top_k: 最终结果数量
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            # 执行完整检索
            result = self.retrieve(query=query, top_k=top_k)
            
            # 构建预览提示
            if result.merged_evidence:
                prompt_preview = self.prompt_builder.build_simple_context(
                    evidence=result.merged_evidence,
                    max_length=500
                )
            else:
                prompt_preview = ""
            
            return {
                "query": query,
                "vector_hits": result.vector_hits,
                "kg_hits": result.kg_hits,
                "merged": [
                    {
                        "id": e.id,
                        "type": e.type,
                        "score": e.score,
                        "content_preview": e.content[:200] + "..." if len(e.content) > 200 else e.content,
                        "sources": e.sources,
                    }
                    for e in result.merged_evidence
                ],
                "prompt_preview": prompt_preview,
                "metadata": result.metadata,
            }
            
        except Exception as e:
            self.logger.error(f"双通道检索测试失败: {e}")
            return {"error": str(e)}
    
    def _load_chunks_from_jsonl(self, file_path: Path) -> List[Dict[str, Any]]:
        """从JSONL文件加载分块数据"""
        import json
        
        chunks = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chunk_data = json.loads(line)
                    chunks.append(chunk_data)
        
        return chunks
    
    def _format_vector_hits(self, vector_results) -> List[Dict[str, Any]]:
        """格式化向量检索结果"""
        return [
            {
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "score": r.score,
                "content": r.text,
                "meta": r.meta,
            }
            for r in vector_results
        ]
    
    def _format_kg_hits(self, kg_results) -> List[Dict[str, Any]]:
        """格式化KG检索结果"""
        return [
            {
                "type": r.type,
                "score": r.score,
                "content": r.content,
                "explanation": r.explanation,
                "data": r.data,
            }
            for r in kg_results
        ]
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        获取管线状态
        
        Returns:
            Dict[str, Any]: 管线状态信息
        """
        try:
            return {
                "config": {
                    "embed_model": self.config.embed_model,
                    "qdrant_collection": self.config.qdrant_collection,
                    "vector_top_k": self.config.vector_top_k,
                    "kg_top_k": self.config.kg_top_k,
                    "use_reranker": self.config.use_reranker,
                },
                "components": {
                    "qdrant_health": self.qdrant_store.health_check(),
                    "neo4j_health": self.neo4j_queries.health_check(),
                    "embedder_loaded": self.embedder.is_loaded,
                    "reranker_enabled": self.reranker.enabled,
                },
                "statistics": {
                    "vector_stats": self.vector_retriever.get_statistics(),
                    "kg_stats": self.kg_retriever.get_statistics(),
                },
            }
            
        except Exception as e:
            self.logger.error(f"获取管线状态失败: {e}")
            return {"error": str(e)}
    
    def ingest_documents_with_kg_linking(self, file_paths: List[str], doc_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        文档入库并建立KG联动
        
        Args:
            file_paths: 文档路径列表
            doc_metadata: 文档元数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            import hashlib
            import os
            from pathlib import Path
            from datetime import datetime
            
            processed_files = 0
            created_chunks = 0
            created_mentions = 0
            
            for file_path in file_paths:
                try:
                    file_path_obj = Path(file_path)
                    
                    if not file_path_obj.exists():
                        self.logger.warning(f"文件不存在: {file_path}")
                        continue
                    
                    # 1. 读取文件内容
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 2. 计算文件信息
                    file_size = os.path.getsize(file_path)
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    
                    # 3. 创建文档节点
                    doc_id = f"doc:{content_hash[:12]}"
                    doc_data = {
                        "id": doc_id,
                        "filename": file_path_obj.name,
                        "filepath": str(file_path),
                        "content_type": "text/plain",
                        "size": file_size,
                        "checksum": content_hash,
                        "metadata": doc_metadata or {},
                        "indexed_at": datetime.now().isoformat()
                    }
                    
                    self.document_store.create_document_node(doc_data)
                    
                    # 4. 文档分块
                    chunks = self.chunker.chunk_text(content, metadata={"doc_id": doc_id})
                    
                    for i, chunk in enumerate(chunks):
                        # 5. 创建块节点
                        chunk_id = f"chunk:{doc_id}:{i:04d}"
                        chunk_hash = hashlib.md5(chunk.content.encode()).hexdigest()
                        
                        chunk_data = {
                            "id": chunk_id,
                            "doc_id": doc_id,
                            "chunk_index": i,
                            "content": chunk.content,
                            "content_hash": chunk_hash,
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                            "vector_id": None,  # 稍后设置
                            "metadata": chunk.metadata,
                            "created_at": datetime.now().isoformat()
                        }
                        
                        self.document_store.create_chunk_node(chunk_data)
                        self.document_store.create_doc_chunk_relationship(doc_id, chunk_id)
                        created_chunks += 1
                        
                        # 6. 实体提取和MENTIONS关系创建
                        try:
                            entities, kg_entity_ids = self.entity_extractor.extract_entities_with_kg_context(
                                chunk.content, 
                                self.neo4j_queries._client
                            )
                            
                            if kg_entity_ids:
                                mention_count = self.document_store.create_chunk_entity_mentions(
                                    chunk_id, 
                                    kg_entity_ids,
                                    [e.confidence for e in entities if e.kg_entity_id]
                                )
                                created_mentions += mention_count
                                
                        except Exception as e:
                            self.logger.warning(f"块实体提取失败 {chunk_id}: {e}")
                    
                    processed_files += 1
                    self.logger.info(f"文档处理完成: {file_path} ({len(chunks)} 块)")
                    
                except Exception as e:
                    self.logger.error(f"处理文件失败 {file_path}: {e}")
                    continue
            
            result = {
                "processed_files": processed_files,
                "created_chunks": created_chunks,
                "created_mentions": created_mentions,
                "kg_linking_enabled": True
            }
            
            self.logger.info(f"KG联动文档入库完成: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"KG联动文档入库失败: {e}")
            return {"error": str(e)}
    
    def get_chunk_kg_context(self, chunk_id: str) -> Dict[str, Any]:
        """
        获取块的KG上下文
        
        Args:
            chunk_id: 块ID
            
        Returns:
            Dict[str, Any]: KG上下文信息
        """
        try:
            # 获取块提及的实体
            mentioned_entities = self.document_store.find_entities_by_chunk(chunk_id)
            
            # 获取块的上下文图谱
            context_graph = self.document_store.get_chunk_context_graph(chunk_id)
            
            return {
                "chunk_id": chunk_id,
                "mentioned_entities": mentioned_entities,
                "context_graph": context_graph,
                "entity_count": len(mentioned_entities)
            }
            
        except Exception as e:
            self.logger.error(f"获取块KG上下文失败: {e}")
            return {"error": str(e)}