#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Pipeline - 完全基于 LangChain 组件的 RAG 管线

使用 LangChain 标准组件：
1. LangChain Embeddings (SiliconFlowEmbeddings)
2. LangChain Vector Store (LangChainQdrantStore)
3. LangChain Retrievers (HybridRetriever)
4. LangChain Text Splitters
"""

import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass

from langchain_core.documents import Document

from .embeddings import create_cached_embeddings
from .vectorstore import LangChainQdrantStore, VectorStoreConfig
from .retriever_factory import create_ensemble_retriever, documents_to_dict
from .chunker import DocumentChunker, DocumentChunk
from .retrievers.retriever_kg import KGRetriever
from .kgstores.neo4j_queries import Neo4jKGQueries

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """RAG 配置 - LangChain 实现"""
    # 基础配置
    base_dir: str = "knowledge_base"
    
    # 文档分块配置
    chunk_size: int = 800
    chunk_overlap: int = 120
    
    # 嵌入配置
    embed_model: str = "BAAI/bge-m3"
    embed_provider: str = "siliconflow"
    embed_cache_dir: Optional[str] = None  # None = 禁用缓存
    
    # Qdrant配置
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "kb_chunks"
    qdrant_api_key: Optional[str] = None
    qdrant_distance: str = "cosine"
    
    # 检索配置
    vector_top_k: int = 12
    kg_top_k: int = 8
    final_top_k: int = 4
    
    # 混合检索配置
    vector_weight: float = 0.7
    kg_weight: float = 0.3
    enable_kg: bool = True
    
    # KG检索配置
    kg_hop: int = 2
    kg_rel_types: List[str] = None
    
    # 向后兼容的旧配置字段（已废弃，但保留以避免破坏现有代码）
    alpha: Optional[float] = None  # 已废弃，使用 vector_weight
    beta: Optional[float] = None   # 已废弃，使用 kg_weight
    use_reranker: bool = False  # 已废弃
    reranker_model: str = "BAAI/bge-reranker-base"  # 已废弃
    max_context_length: int = 4000  # 已废弃
    citation_style: str = "numbered"  # 已废弃


@dataclass
class RAGRetrievalResult:
    """RAG 检索结果"""
    query: str
    documents: List[Document]  # LangChain Document 对象
    metadata: Dict[str, Any]


class RAGPipeline:
    """
    基于 LangChain 的 RAG 管线
    
    完全使用 LangChain 组件重构，提供：
    1. 标准化的 Embeddings、VectorStore、Retrievers
    2. 简化的 API 和更好的可维护性
    3. 更强的生态集成能力
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        """
        初始化 RAG 管线
        
        Args:
            config: RAG 配置
        """
        self.config = config or RAGConfig()
        self.logger = logging.getLogger(__name__)
        
        # 向后兼容：处理旧配置字段
        if self.config.alpha is not None:
            self.config.vector_weight = self.config.alpha
        if self.config.beta is not None:
            self.config.kg_weight = self.config.beta
        
        # 初始化组件
        self._init_components()
    
    def _init_components(self):
        """初始化所有组件"""
        try:
            self.logger.info("初始化 RAG 组件...")
            
            # 1. 文档分块器（使用 LangChain TextSplitter）
            self.chunker = DocumentChunker(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap
            )
            self.logger.info(f"✅ 文档分块器: chunk_size={self.config.chunk_size}")
            
            # 2. Embeddings（使用 LangChain Embeddings + Cache）
            self.embeddings = create_cached_embeddings(
                model_name=self.config.embed_model,
                provider=self.config.embed_provider,
                cache_dir=self.config.embed_cache_dir,
                namespace=self.config.embed_model.replace("/", "_")
            )
            self.logger.info(f"✅ Embeddings: model={self.config.embed_model}, cached={self.config.embed_cache_dir is not None}")
            
            # 3. Vector Store（使用 LangChain Qdrant）
            vector_config = VectorStoreConfig(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
                collection_name=self.config.qdrant_collection,
                distance=self.config.qdrant_distance
            )
            self.vector_store = LangChainQdrantStore(
                embeddings=self.embeddings,
                config=vector_config
            )
            self.logger.info(f"✅ Vector Store: collection={self.config.qdrant_collection}")
            
            # 4. KG 检索器（保留原有实现）
            if self.config.enable_kg:
                self.neo4j_queries = Neo4jKGQueries()
                self.kg_retriever = KGRetriever(
                    neo4j_queries=self.neo4j_queries
                )
                self.logger.info(f"✅ KG Retriever: enabled")
            else:
                self.kg_retriever = None
                self.logger.info(f"⚠️  KG Retriever: disabled")
            
            # 5. 混合检索器（使用 LangChain Retriever）
            vector_retriever = self.vector_store.as_retriever(
                search_kwargs={"k": self.config.vector_top_k}
            )
            
            self.hybrid_retriever = create_ensemble_retriever(
                vector_retriever=vector_retriever,
                kg_retriever=self.kg_retriever if self.config.enable_kg else None,
                vector_weight=self.config.vector_weight,
                kg_weight=self.config.kg_weight,
                top_k=self.config.final_top_k
            )
            self.logger.info(f"✅ Hybrid Retriever: vector_weight={self.config.vector_weight}, kg_weight={self.config.kg_weight}")
            
            self.logger.info("🎉 RAG 组件初始化完成!")
            
        except Exception as e:
            self.logger.error(f"❌ RAG 组件初始化失败: {e}")
            raise
    
    def ingest_documents(
        self,
        file_paths: List[Union[str, Path]],
        doc_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        文档入库（分块）
        
        Args:
            file_paths: 文档文件路径列表
            doc_metadata: 文档元数据
            
        Returns:
            Dict[str, Any]: 入库统计
        """
        try:
            self.logger.info(f"开始文档入库: {len(file_paths)} 个文件")
            
            all_chunks = []
            stats = {
                "total_files": len(file_paths),
                "processed_files": 0,
                "total_chunks": 0,
                "failed_files": [],
            }
            
            for file_path in file_paths:
                try:
                    file_path = Path(file_path)
                    doc_id = file_path.stem
                    
                    # 合并元数据
                    meta = doc_metadata.copy() if doc_metadata else {}
                    meta.update({
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "doc_id": doc_id
                    })
                    
                    # 分块
                    chunks = self.chunker.chunk_file(file_path, doc_id, meta)
                    all_chunks.extend(chunks)
                    
                    stats["processed_files"] += 1
                    self.logger.debug(f"✅ {file_path.name}: {len(chunks)} 块")
                    
                except Exception as e:
                    self.logger.error(f"❌ 文件处理失败 {file_path}: {e}")
                    stats["failed_files"].append(str(file_path))
            
            stats["total_chunks"] = len(all_chunks)
            
            # 保存分块结果
            chunks_file = Path(self.config.base_dir) / "chunks" / "latest_chunks.jsonl"
            chunks_file.parent.mkdir(parents=True, exist_ok=True)
            self.chunker.save_chunks_to_jsonl(all_chunks, chunks_file)
            
            self.logger.info(
                f"✅ 文档入库完成: {stats['processed_files']}/{stats['total_files']} 个文件, "
                f"{stats['total_chunks']} 个分块"
            )
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ 文档入库失败: {e}")
            raise
    
    def index_documents(
        self,
        chunk_file: Optional[Union[str, Path]] = None,
        force_recreate: bool = False
    ) -> Dict[str, Any]:
        """
        文档索引（向量化并存入 Qdrant）
        
        Args:
            chunk_file: 分块文件路径（None = 使用最新分块）
            force_recreate: 是否强制重新创建集合
            
        Returns:
            Dict[str, Any]: 索引统计
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
            self.logger.info(f"读取 {len(chunks_data)} 个分块")
            
            # 2. 转换为 LangChain Document
            documents = []
            for chunk in chunks_data:
                doc = Document(
                    page_content=chunk["text"],
                    metadata={
                        "chunk_id": chunk["chunk_id"],
                        "doc_id": chunk["doc_id"],
                        **chunk.get("meta", {})
                    }
                )
                documents.append(doc)
            
            # 3. 创建/更新 Qdrant 集合
            collection_created = self.vector_store.create_collection(
                force_recreate=force_recreate
            )
            
            if not collection_created:
                raise RuntimeError("Qdrant 集合创建失败")
            
            self.logger.info(f"✅ Qdrant 集合: {self.config.qdrant_collection}")
            
            # 4. 批量添加文档（LangChain 会自动调用 embeddings）
            self.logger.info("开始向量化和索引...")
            
            doc_ids = [chunk["chunk_id"] for chunk in chunks_data]
            added_ids = self.vector_store.add_documents(
                documents=documents,
                ids=doc_ids,
                batch_size=32
            )
            
            # 5. 获取集合信息
            collection_info = self.vector_store.get_collection_info()
            
            stats = {
                "indexed_chunks": len(added_ids),
                "collection_name": self.config.qdrant_collection,
                "collection_info": collection_info,
                "embedding_model": self.config.embed_model,
                "force_recreate": force_recreate,
            }
            
            self.logger.info(
                f"✅ 文档索引完成: {stats['indexed_chunks']} 个分块, "
                f"总点数={collection_info.get('points_count', 'unknown')}"
            )
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ 文档索引失败: {e}")
            raise
    
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> RAGRetrievalResult:
        """
        检索相关文档（使用 LangChain Retriever）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量（None = 使用配置默认值）
            filters: 元数据过滤条件
            
        Returns:
            RAGRetrievalResult: 检索结果
        """
        try:
            top_k = top_k or self.config.final_top_k
            
            self.logger.debug(f"开始检索: query='{query[:50]}...', top_k={top_k}")
            
            # 使用 LangChain Retriever 检索
            documents = self.hybrid_retriever.get_relevant_documents(query)
            
            # 限制结果数量
            documents = documents[:top_k]
            
            # 构建结果
            result = RAGRetrievalResult(
                query=query,
                documents=documents,
                metadata={
                    "retrieved_count": len(documents),
                    "top_k": top_k,
                    "config": {
                        "vector_weight": self.config.vector_weight,
                        "kg_weight": self.config.kg_weight,
                        "enable_kg": self.config.enable_kg,
                    }
                }
            )
            
            self.logger.info(f"✅ 检索完成: {len(documents)} 个文档")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 检索失败: {e}")
            raise
    
    def retrieve_as_dict(
        self,
        query: str,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        检索并返回字典格式（兼容现有接口）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            Dict[str, Any]: 检索结果字典
        """
        try:
            result = self.retrieve(query, top_k)
            
            return {
                "query": result.query,
                "documents": documents_to_dict(result.documents),
                "count": len(result.documents),
                "metadata": result.metadata
            }
            
        except Exception as e:
            self.logger.error(f"❌ 检索失败: {e}")
            return {
                "query": query,
                "documents": [],
                "count": 0,
                "metadata": {"error": str(e)}
            }
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        获取管线状态
        
        Returns:
            Dict[str, Any]: 状态信息
        """
        try:
            # 获取 Qdrant 集合信息
            collection_info = self.vector_store.get_collection_info()
            
            # KG 健康检查
            kg_health = False
            if self.kg_retriever:
                try:
                    kg_health = self.neo4j_queries.health_check()
                except:
                    pass
            
            return {
                "pipeline_type": "LangChain",
                "config": {
                    "embed_model": self.config.embed_model,
                    "qdrant_collection": self.config.qdrant_collection,
                    "vector_top_k": self.config.vector_top_k,
                    "kg_top_k": self.config.kg_top_k,
                    "enable_kg": self.config.enable_kg,
                },
                "components": {
                    "embeddings": "SiliconFlowEmbeddings",
                    "vector_store": "LangChainQdrantStore",
                    "retriever": "HybridRetriever",
                    "qdrant_health": collection_info.get("points_count") is not None,
                    "kg_health": kg_health,
                },
                "collection_info": collection_info,
            }
            
        except Exception as e:
            self.logger.error(f"获取管线状态失败: {e}")
            return {"error": str(e)}
    
    def _load_chunks_from_jsonl(self, file_path: Path) -> List[Dict[str, Any]]:
        """从 JSONL 文件加载分块数据"""
        import json
        
        chunks = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chunk_data = json.loads(line)
                    chunks.append(chunk_data)
        
        return chunks


# ============================================================================
# 工厂函数 - 向后兼容
# ============================================================================

def create_rag_pipeline(
    embed_model: str = "BAAI/bge-m3",
    qdrant_url: str = "http://qdrant:6333",
    qdrant_collection: str = "kb_chunks",
    enable_kg: bool = True,
    **kwargs
) -> RAGPipeline:
    """
    创建 RAG 管线（工厂函数）
    
    Args:
        embed_model: 嵌入模型名称
        qdrant_url: Qdrant 服务 URL
        qdrant_collection: Qdrant 集合名称
        enable_kg: 是否启用 KG 检索
        **kwargs: 额外配置参数
        
    Returns:
        RAGPipeline: RAG 管线实例
    """
    config = RAGConfig(
        embed_model=embed_model,
        qdrant_url=qdrant_url,
        qdrant_collection=qdrant_collection,
        enable_kg=enable_kg,
        **kwargs
    )
    
    return RAGPipeline(config)
