#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG API端点

提供知识库管理、文档索引、检索测试等API接口
按照IMPROOVE_GUIDE.md的API合同设计
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import tempfile
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ...core.settings import get_settings
from ...infrastructure.rag import RAGPipeline, RAGConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


# Pydantic 模型
class DocumentInfo(BaseModel):
    """文档信息"""
    filename: str
    size: int
    created_at: str
    modified_at: str
    indexed: bool
    chunk_count: Optional[int] = None


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentInfo]
    total_count: int
    indexed_count: int


class IndexRequest(BaseModel):
    """索引请求"""
    force_recreate: bool = False
    documents: Optional[List[str]] = None  # 特定文档列表，None表示全部


class IndexResponse(BaseModel):
    """索引响应"""
    success: bool
    message: str
    statistics: Dict[str, Any]


class TestVectorRequest(BaseModel):
    """向量检索测试请求"""
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class TestKGRequest(BaseModel):
    """KG检索测试请求"""
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    hop: int = Field(default=2, ge=1, le=5)
    rel_types: Optional[List[str]] = None


class TestDualRequest(BaseModel):
    """双通道检索测试请求"""
    query: str
    top_k: int = Field(default=4, ge=1, le=10)
    include_kg: bool = True


# 全局RAG管线实例（懒加载）
_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """获取RAG管线实例（依赖注入）"""
    global _rag_pipeline
    
    if _rag_pipeline is None:
        settings = get_settings()
        
        # 构建RAG配置
        config = RAGConfig(
            base_dir=settings.rag.base_dir,
            chunk_size=settings.rag.chunk_size,
            chunk_overlap=settings.rag.chunk_overlap,
            embed_model=settings.rag.embed_model,
            embed_provider=settings.rag.embed_provider,
            qdrant_url=settings.qdrant.url,
            qdrant_collection=settings.qdrant.collection,
            qdrant_distance=settings.qdrant.distance,
            vector_top_k=settings.rag.vector_top_k,
            kg_top_k=settings.rag.kg_top_k,
            final_top_k=settings.rag.top_k,
            alpha=settings.rag.alpha,
            beta=settings.rag.beta,
            use_reranker=settings.rag.use_reranker,
            kg_hop=settings.rag.hop,
            kg_rel_types=settings.rag.rel_types,
        )
        
        _rag_pipeline = RAGPipeline(config)
        logger.info("RAG管线初始化完成")
    
    return _rag_pipeline


@router.get("/docs", response_model=DocumentListResponse)
async def list_documents(rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)):
    """
    列出文档
    
    返回知识库中的所有文档信息，包括文件名、大小、更新时间、索引状态等
    """
    try:
        settings = get_settings()
        raw_dir = Path(settings.rag.base_dir) / "raw"
        
        if not raw_dir.exists():
            return DocumentListResponse(
                documents=[],
                total_count=0,
                indexed_count=0
            )
        
        documents = []
        indexed_count = 0
        
        # 扫描原始文档目录
        for file_path in raw_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                stat = file_path.stat()
                
                # 检查是否已索引（简化版本：检查chunks目录中是否有对应的JSONL文件）
                chunks_dir = Path(settings.rag.base_dir) / "chunks"
                chunk_file = chunks_dir / f"{file_path.stem}_chunks.jsonl"
                indexed = chunk_file.exists()
                
                if indexed:
                    indexed_count += 1
                
                doc_info = DocumentInfo(
                    filename=file_path.name,
                    size=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    indexed=indexed,
                    chunk_count=None  # TODO: 从JSONL文件读取块数量
                )
                documents.append(doc_info)
        
        return DocumentListResponse(
            documents=documents,
            total_count=len(documents),
            indexed_count=indexed_count
        )
        
    except Exception as e:
        logger.error(f"列出文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出文档失败: {str(e)}")


@router.post("/docs")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    auto_index: bool = Form(default=False),
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    上传文档
    
    支持多文件上传，可选择是否自动索引
    """
    try:
        settings = get_settings()
        raw_dir = Path(settings.rag.base_dir) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        uploaded_files = []
        failed_files = []
        
        for file in files:
            try:
                # 检查文件类型
                allowed_extensions = {'.txt', '.md', '.markdown', '.html', '.htm', '.pdf'}
                file_path = raw_dir / file.filename
                
                if file_path.suffix.lower() not in allowed_extensions:
                    failed_files.append({
                        "filename": file.filename,
                        "error": f"不支持的文件类型: {file_path.suffix}"
                    })
                    continue
                
                # 保存文件
                content = await file.read()
                file_path.write_bytes(content)
                
                uploaded_files.append({
                    "filename": file.filename,
                    "size": len(content),
                    "path": str(file_path)
                })
                
                logger.info(f"文件上传成功: {file.filename}")
                
            except Exception as e:
                logger.error(f"文件上传失败 {file.filename}: {e}")
                failed_files.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        # 如果需要自动索引，添加后台任务
        if auto_index and uploaded_files:
            file_paths = [f["path"] for f in uploaded_files]
            background_tasks.add_task(
                _background_index_documents,
                rag_pipeline,
                file_paths
            )
        
        return {
            "success": True,
            "message": f"上传完成: 成功 {len(uploaded_files)} 个，失败 {len(failed_files)} 个",
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "auto_index": auto_index
        }
        
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档上传失败: {str(e)}")


@router.delete("/docs/{filename}")
async def delete_document(
    filename: str,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    删除文档
    
    同时删除原始文件、分块数据和向量索引
    """
    try:
        settings = get_settings()
        raw_dir = Path(settings.rag.base_dir) / "raw"
        file_path = raw_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文档不存在: {filename}")
        
        # 删除原始文件
        file_path.unlink()
        
        # 删除分块文件
        chunks_dir = Path(settings.rag.base_dir) / "chunks"
        chunk_file = chunks_dir / f"{file_path.stem}_chunks.jsonl"
        if chunk_file.exists():
            chunk_file.unlink()
        
        # TODO: 从Qdrant中删除对应的向量
        # 这需要根据doc_id删除相关的点
        
        return {
            "success": True,
            "message": f"文档删除成功: {filename}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@router.post("/reindex", response_model=IndexResponse)
async def reindex_documents(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    重建索引
    
    支持全量或增量索引，可强制重新创建集合
    """
    try:
        settings = get_settings()
        raw_dir = Path(settings.rag.base_dir) / "raw"
        
        if not raw_dir.exists():
            raise HTTPException(status_code=400, detail="原始文档目录不存在")
        
        # 确定要处理的文档
        if request.documents:
            # 指定文档列表
            file_paths = []
            for filename in request.documents:
                file_path = raw_dir / filename
                if file_path.exists():
                    file_paths.append(file_path)
                else:
                    logger.warning(f"指定的文档不存在: {filename}")
        else:
            # 全部文档
            file_paths = [
                f for f in raw_dir.iterdir()
                if f.is_file() and not f.name.startswith('.')
                and f.suffix.lower() in {'.txt', '.md', '.markdown', '.html', '.htm', '.pdf'}
            ]
        
        if not file_paths:
            return IndexResponse(
                success=False,
                message="没有找到可索引的文档",
                statistics={}
            )
        
        # 启动后台索引任务
        background_tasks.add_task(
            _background_full_index,
            rag_pipeline,
            file_paths,
            request.force_recreate
        )
        
        return IndexResponse(
            success=True,
            message=f"索引任务已启动，将处理 {len(file_paths)} 个文档",
            statistics={
                "documents_to_process": len(file_paths),
                "force_recreate": request.force_recreate
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重建索引失败: {e}")
        raise HTTPException(status_code=500, detail=f"重建索引失败: {str(e)}")


@router.post("/test_vector")
async def test_vector_retrieval(
    request: TestVectorRequest,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    测试向量检索
    
    返回向量通道的检索结果
    """
    try:
        result = rag_pipeline.test_vector_retrieval(
            query=request.query,
            top_k=request.top_k
        )
        
        return result
        
    except Exception as e:
        logger.error(f"向量检索测试失败: {e}")
        raise HTTPException(status_code=500, detail=f"向量检索测试失败: {str(e)}")


@router.post("/test_kg")
async def test_kg_retrieval(
    request: TestKGRequest,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    测试KG检索
    
    返回知识图谱检索的结果
    """
    try:
        result = rag_pipeline.test_kg_retrieval(
            query=request.query,
            hop=request.hop,
            top_k=request.top_k
        )
        
        return result
        
    except Exception as e:
        logger.error(f"KG检索测试失败: {e}")
        raise HTTPException(status_code=500, detail=f"KG检索测试失败: {str(e)}")


@router.post("/test_dual")
async def test_dual_retrieval(
    request: TestDualRequest,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    测试双通道检索
    
    返回合并/复排后的最终证据包，符合IMPROOVE_GUIDE.md的标准响应格式
    """
    try:
        result = rag_pipeline.test_dual_retrieval(
            query=request.query,
            top_k=request.top_k
        )
        
        return result
        
    except Exception as e:
        logger.error(f"双通道检索测试失败: {e}")
        raise HTTPException(status_code=500, detail=f"双通道检索测试失败: {str(e)}")


@router.get("/status")
async def get_rag_status(rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)):
    """
    获取RAG系统状态
    
    返回各组件的健康状态和统计信息
    """
    try:
        status = rag_pipeline.get_pipeline_status()
        return status
        
    except Exception as e:
        logger.error(f"获取RAG状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取RAG状态失败: {str(e)}")


# 后台任务函数
async def _background_index_documents(rag_pipeline: RAGPipeline, file_paths: List[str]):
    """后台索引文档任务"""
    try:
        logger.info(f"开始后台索引任务: {len(file_paths)} 个文件")
        
        # 1. 文档入库
        ingest_result = rag_pipeline.ingest_documents(
            file_paths=file_paths,
            doc_metadata={"indexed_at": datetime.now().isoformat()}
        )
        
        # 2. 建立索引
        index_result = rag_pipeline.index_documents()
        
        logger.info(f"后台索引任务完成: 处理 {ingest_result['processed_files']} 个文件")
        
    except Exception as e:
        logger.error(f"后台索引任务失败: {e}")


async def _background_full_index(rag_pipeline: RAGPipeline, file_paths: List[Path], force_recreate: bool):
    """后台全量索引任务"""
    try:
        logger.info(f"开始后台全量索引任务: {len(file_paths)} 个文件")
        
        # 1. 文档入库
        ingest_result = rag_pipeline.ingest_documents(
            file_paths=[str(p) for p in file_paths],
            doc_metadata={"reindexed_at": datetime.now().isoformat()}
        )
        
        # 2. 建立索引
        index_result = rag_pipeline.index_documents(force_recreate=force_recreate)
        
        logger.info(f"后台全量索引任务完成: 处理 {ingest_result['processed_files']} 个文件")
        
    except Exception as e:
        logger.error(f"后台全量索引任务失败: {e}")


@router.post("/kg_linking/ingest")
async def ingest_documents_with_kg_linking(
    file_paths: List[str] = Form(...),
    metadata: Optional[str] = Form(None),
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    文档入库并建立KG联动
    
    Args:
        file_paths: 文档路径列表
        metadata: 文档元数据（JSON字符串）
        rag_pipeline: RAG管线实例
        
    Returns:
        处理结果，包括创建的节点和关系统计
    """
    try:
        import json
        
        # 解析元数据
        doc_metadata = {}
        if metadata:
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="元数据格式错误")
        
        # 执行KG联动入库
        result = rag_pipeline.ingest_documents_with_kg_linking(
            file_paths=file_paths,
            doc_metadata=doc_metadata
        )
        
        return {
            "message": "KG联动文档入库完成",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"KG联动文档入库失败: {e}")
        raise HTTPException(status_code=500, detail=f"KG联动文档入库失败: {str(e)}")


@router.get("/kg_linking/chunk/{chunk_id}")
async def get_chunk_kg_context(
    chunk_id: str,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    获取块的KG上下文
    
    Args:
        chunk_id: 块ID
        rag_pipeline: RAG管线实例
        
    Returns:
        块的KG上下文信息
    """
    try:
        context = rag_pipeline.get_chunk_kg_context(chunk_id)
        
        return {
            "chunk_id": chunk_id,
            "kg_context": context,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取块KG上下文失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取块KG上下文失败: {str(e)}")


@router.get("/kg_linking/statistics")
async def get_kg_linking_statistics(
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    获取KG联动统计信息
    
    Returns:
        KG联动的统计数据
    """
    try:
        # 获取Neo4j中的文档、块、关系统计
        stats_query = """
        MATCH (d:Document) 
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
        RETURN 
            count(DISTINCT d) as document_count,
            count(DISTINCT c) as chunk_count,
            count(DISTINCT e) as mentioned_entity_count,
            count(DISTINCT c-[:MENTIONS]->e) as mentions_count
        """
        
        result = rag_pipeline.neo4j_queries._client.execute_cypher(stats_query)
        
        if result and result[0]:
            stats = result[0]
        else:
            stats = {
                "document_count": 0,
                "chunk_count": 0,
                "mentioned_entity_count": 0,
                "mentions_count": 0
            }
        
        return {
            "kg_linking_statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取KG联动统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取KG联动统计失败: {str(e)}")