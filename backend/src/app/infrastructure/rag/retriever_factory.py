#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangChain Retrievers Integration - 检索器 LangChain 集成

提供基于 LangChain 的检索器实现：
1. EnsembleRetriever - 多源检索合并
2. 自定义 KG Retriever 适配
3. 与现有 KG 检索逻辑集成
4. 重排序支持
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pydantic import Field

logger = logging.getLogger(__name__)


class KGRetrieverAdapter(BaseRetriever):
    """
    知识图谱检索器适配器
    
    将现有的 KGRetriever 适配为 LangChain Retriever 接口
    """
    
    kg_retriever: Any = Field(description="底层 KG 检索器")
    top_k: int = Field(default=5, description="返回结果数量")
    score_threshold: Optional[float] = Field(default=None, description="分数阈值")
    
    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """
        获取相关文档（LangChain 接口）
        
        Args:
            query: 查询文本
            run_manager: 回调管理器
            
        Returns:
            List[Document]: 文档列表
        """
        try:
            # 调用底层 KG 检索器
            kg_results = self.kg_retriever.search(
                query=query,
                top_k=self.top_k,
                score_threshold=self.score_threshold
            )
            
            # 转换为 LangChain Document 格式
            documents = []
            for result in kg_results:
                doc = Document(
                    page_content=result.content,
                    metadata={
                        "type": "kg",
                        "kg_type": result.type,
                        "score": result.score,
                        "explanation": result.explanation,
                        "source": "knowledge_graph",
                        **result.data
                    }
                )
                documents.append(doc)
            
            logger.debug(f"KG 检索完成: {len(documents)} 个文档")
            return documents
            
        except Exception as e:
            logger.error(f"KG 检索失败: {e}")
            return []


class HybridRetriever(BaseRetriever):
    """
    混合检索器 - 基于 LangChain EnsembleRetriever
    
    结合向量检索和知识图谱检索，提供：
    1. 加权合并策略
    2. 分数归一化
    3. 去重处理
    4. 可选的重排序
    """
    
    retrievers: List[BaseRetriever] = Field(description="检索器列表")
    weights: List[float] = Field(description="检索器权重")
    top_k: int = Field(default=10, description="最终返回结果数量")
    score_threshold: Optional[float] = Field(default=None, description="分数阈值")
    reranker: Optional[Callable] = Field(default=None, description="重排序函数")
    
    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """
        获取相关文档（混合检索）
        
        Args:
            query: 查询文本
            run_manager: 回调管理器
            
        Returns:
            List[Document]: 合并后的文档列表
        """
        try:
            # 1. 从所有检索器获取结果
            all_docs = []
            for retriever, weight in zip(self.retrievers, self.weights):
                try:
                    docs = retriever.get_relevant_documents(
                        query,
                        run_manager=run_manager
                    )
                    
                    # 应用权重到分数
                    weighted_docs = []
                    for doc in docs:
                        weighted_doc = Document(
                            page_content=doc.page_content,
                            metadata={
                                **doc.metadata,
                                "retriever_weight": weight,
                                "original_score": doc.metadata.get("score", 1.0),
                                "weighted_score": doc.metadata.get("score", 1.0) * weight
                            }
                        )
                        weighted_docs.append(weighted_doc)
                    
                    all_docs.extend(weighted_docs)
                    logger.debug(f"检索器 {retriever.__class__.__name__} 返回 {len(docs)} 个文档")
                    
                except Exception as e:
                    logger.error(f"检索器 {retriever.__class__.__name__} 失败: {e}")
                    continue
            
            if not all_docs:
                logger.warning("所有检索器都未返回结果")
                return []
            
            # 2. 去重和合并
            merged_docs = self._merge_and_deduplicate(all_docs)
            
            # 3. 应用分数阈值
            if self.score_threshold is not None:
                merged_docs = [
                    doc for doc in merged_docs
                    if doc.metadata.get("weighted_score", 0) >= self.score_threshold
                ]
            
            # 4. 重排序（如果提供）
            if self.reranker is not None:
                merged_docs = self.reranker(query, merged_docs)
            
            # 5. 按分数排序并限制结果数量
            merged_docs.sort(
                key=lambda x: x.metadata.get("weighted_score", 0),
                reverse=True
            )
            final_docs = merged_docs[:self.top_k]
            
            logger.info(f"混合检索完成: {len(final_docs)} 个文档（来自 {len(all_docs)} 个原始结果）")
            return final_docs
            
        except Exception as e:
            logger.error(f"混合检索失败: {e}")
            return []
    
    def _merge_and_deduplicate(self, documents: List[Document]) -> List[Document]:
        """
        合并和去重文档
        
        Args:
            documents: 文档列表
            
        Returns:
            List[Document]: 去重后的文档列表
        """
        # 使用内容哈希进行去重
        seen_content = {}
        merged_docs = []
        
        for doc in documents:
            # 生成内容指纹
            content_hash = self._get_content_hash(doc.page_content)
            
            if content_hash in seen_content:
                # 已存在，合并分数
                existing_doc = seen_content[content_hash]
                existing_score = existing_doc.metadata.get("weighted_score", 0)
                new_score = doc.metadata.get("weighted_score", 0)
                
                # 累加分数
                combined_score = existing_score + new_score * 0.5  # 重复内容给予部分权重
                
                # 更新元数据
                existing_doc.metadata["weighted_score"] = combined_score
                existing_doc.metadata["duplicate_count"] = existing_doc.metadata.get("duplicate_count", 1) + 1
                
                # 合并来源
                sources = existing_doc.metadata.get("sources", [existing_doc.metadata.get("source", "unknown")])
                new_source = doc.metadata.get("source", "unknown")
                if new_source not in sources:
                    sources.append(new_source)
                existing_doc.metadata["sources"] = sources
            else:
                # 新内容
                doc.metadata["duplicate_count"] = 1
                doc.metadata["sources"] = [doc.metadata.get("source", "unknown")]
                seen_content[content_hash] = doc
                merged_docs.append(doc)
        
        return merged_docs
    
    @staticmethod
    def _get_content_hash(content: str) -> str:
        """
        获取内容哈希
        
        Args:
            content: 文本内容
            
        Returns:
            str: 内容哈希
        """
        import hashlib
        # 简化内容进行哈希（去除标点和空格）
        simplified = ''.join(c.lower() for c in content if c.isalnum())
        return hashlib.md5(simplified.encode('utf-8')).hexdigest()[:16]


def create_ensemble_retriever(
    vector_retriever: BaseRetriever,
    kg_retriever: Optional[Any] = None,
    vector_weight: float = 0.7,
    kg_weight: float = 0.3,
    top_k: int = 10,
    score_threshold: Optional[float] = None,
    reranker: Optional[Callable] = None
) -> HybridRetriever:
    """
    创建 Ensemble 检索器
    
    Args:
        vector_retriever: 向量检索器（LangChain Retriever）
        kg_retriever: KG 检索器（自定义实现）
        vector_weight: 向量检索权重
        kg_weight: KG 检索权重
        top_k: 最终返回结果数量
        score_threshold: 分数阈值
        reranker: 重排序函数
        
    Returns:
        HybridRetriever: 混合检索器
    """
    # 构建检索器列表和权重
    retrievers = [vector_retriever]
    weights = [vector_weight]
    
    # 添加 KG 检索器（如果提供）
    if kg_retriever is not None:
        kg_adapter = KGRetrieverAdapter(
            kg_retriever=kg_retriever,
            top_k=top_k
        )
        retrievers.append(kg_adapter)
        weights.append(kg_weight)
    
    # 归一化权重
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]
    
    logger.info(
        f"创建 EnsembleRetriever: "
        f"retrievers={len(retrievers)}, "
        f"weights={weights}, "
        f"top_k={top_k}"
    )
    
    return HybridRetriever(
        retrievers=retrievers,
        weights=weights,
        top_k=top_k,
        score_threshold=score_threshold,
        reranker=reranker
    )


def create_reranker(
    model_name: str = "BAAI/bge-reranker-base",
    top_k: Optional[int] = None
) -> Callable:
    """
    创建重排序函数
    
    Args:
        model_name: 重排序模型名称
        top_k: 重排序后返回的结果数量
        
    Returns:
        Callable: 重排序函数
    """
    def rerank(query: str, documents: List[Document]) -> List[Document]:
        """
        重排序文档
        
        Args:
            query: 查询文本
            documents: 文档列表
            
        Returns:
            List[Document]: 重排序后的文档列表
        """
        try:
            # TODO: 实现实际的重排序逻辑
            # 这里需要调用重排序模型 API
            logger.warning(f"重排序功能暂未实现（model={model_name}），返回原始结果")
            
            # 临时实现：按现有分数排序
            sorted_docs = sorted(
                documents,
                key=lambda x: x.metadata.get("weighted_score", 0),
                reverse=True
            )
            
            if top_k is not None:
                sorted_docs = sorted_docs[:top_k]
            
            return sorted_docs
            
        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return documents
    
    return rerank


@dataclass
class RetrievalResult:
    """检索结果数据类"""
    documents: List[Document]
    metadata: Dict[str, Any]


def documents_to_dict(documents: List[Document]) -> List[Dict[str, Any]]:
    """
    将 LangChain Document 转换为字典格式
    
    Args:
        documents: LangChain Document 列表
        
    Returns:
        List[Dict[str, Any]]: 字典列表
    """
    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata
        }
        for doc in documents
    ]


def dict_to_documents(data: List[Dict[str, Any]]) -> List[Document]:
    """
    将字典格式转换为 LangChain Document
    
    Args:
        data: 字典列表
        
    Returns:
        List[Document]: LangChain Document 列表
    """
    return [
        Document(
            page_content=item.get("content", ""),
            metadata=item.get("metadata", {})
        )
        for item in data
    ]







