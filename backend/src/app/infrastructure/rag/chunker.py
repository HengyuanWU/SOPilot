#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document Chunker - 基于 LangChain RecursiveCharacterTextSplitter 的文档分块器

使用 LangChain TextSplitter 进行文档分块：
1. 递归分层：优先按段落，再按句子，最后按字符
2. 中文友好：针对中文标点符号优化
3. 更智能的边界检测
"""

import hashlib
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """文档分块数据类"""
    chunk_id: str
    doc_id: str
    text: str
    meta: Dict[str, Any]
    tokens: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None


class DocumentChunker:
    """
    文档分块器 - LangChain RecursiveCharacterTextSplitter 实现
    
    相比原实现的改进：
    1. 递归分层：优先按段落，再按句子，最后按字符
    2. 中文友好：针对中文标点符号优化
    3. 更智能的边界检测
    """
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        """
        初始化分块器
        
        Args:
            chunk_size: 分块大小（默认800，适合中文/中英混排）
            chunk_overlap: 重叠大小（默认120）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 中文优化的分隔符（递归优先级从高到低）
        separators = [
            "\n\n",      # 段落分隔
            "\n",        # 行分隔
            "。",        # 中文句号
            "！",        # 中文感叹号
            "？",        # 中文问号
            "；",        # 中文分号
            "，",        # 中文逗号
            ".",         # 英文句号
            "!",         # 英文感叹号
            "?",         # 英文问号
            ";",         # 英文分号
            ",",         # 英文逗号
            " ",         # 空格
            ""           # 最后按字符分割
        ]
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False,
            keep_separator=True  # 保留分隔符以保持语义完整性
        )
        
        logger.info(f"初始化文档分块器: chunk_size={chunk_size}, overlap={chunk_overlap}")
    
    def chunk_text(self, text: str, doc_id: str, meta: Dict[str, Any] = None) -> List[DocumentChunk]:
        """
        对文本进行分块
        
        Args:
            text: 要分块的文本
            doc_id: 文档ID
            meta: 元数据
            
        Returns:
            List[DocumentChunk]: 分块结果列表
        """
        meta = meta or {}
        
        if not text or not text.strip():
            logger.warning(f"文档 {doc_id} 内容为空，跳过分块")
            return []
        
        # 使用 LangChain 分块
        langchain_docs = self.splitter.create_documents(
            texts=[text],
            metadatas=[meta]
        )
        
        # 转换为 DocumentChunk 格式
        chunks = []
        for chunk_index, lc_doc in enumerate(langchain_docs):
            chunk_text = lc_doc.page_content
            
            if not chunk_text.strip():
                continue
            
            # 计算在原文中的位置（近似）
            start_char = text.find(chunk_text[:50]) if len(chunk_text) >= 50 else text.find(chunk_text)
            if start_char == -1:
                start_char = 0  # 无法定位时使用默认值
            end_char = start_char + len(chunk_text)
            
            chunk_id = self._generate_chunk_id(doc_id, chunk_index, chunk_text)
            
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                text=chunk_text,
                meta={
                    **lc_doc.metadata,
                    "chunk_index": chunk_index,
                    "start_char": start_char,
                    "end_char": end_char,
                },
                tokens=self._estimate_tokens(chunk_text),
                start_char=start_char,
                end_char=end_char
            )
            chunks.append(chunk)
        
        logger.info(f"文档 {doc_id} 分块完成: {len(chunks)} 个块")
        return chunks
    
    def chunk_file(self, file_path: Union[str, Path], doc_id: str = None, 
                   meta: Dict[str, Any] = None) -> List[DocumentChunk]:
        """
        对文件进行分块
        
        Args:
            file_path: 文件路径
            doc_id: 文档ID（如果为空则使用文件名）
            meta: 元数据
            
        Returns:
            List[DocumentChunk]: 分块结果列表
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='gb2312') as f:
                    content = f.read()
        
        # 生成 doc_id
        if doc_id is None:
            doc_id = file_path.stem
        
        # 合并元数据
        file_meta = meta or {}
        file_meta.update({
            "source": str(file_path),
            "filename": file_path.name,
            "file_type": file_path.suffix.lstrip('.')
        })
        
        return self.chunk_text(content, doc_id, file_meta)
    
    def save_chunks_to_jsonl(self, chunks: List[DocumentChunk], output_path: Union[str, Path]) -> None:
        """
        将分块结果保存为JSONL格式
        
        Args:
            chunks: 分块列表
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                chunk_dict = {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "meta": chunk.meta,
                    "tokens": chunk.tokens,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                }
                f.write(json.dumps(chunk_dict, ensure_ascii=False) + '\n')
        
        logger.info(f"分块结果已保存到: {output_path}")
    
    def _generate_chunk_id(self, doc_id: str, chunk_index: int, chunk_text: str) -> str:
        """
        生成块ID
        
        Args:
            doc_id: 文档ID
            chunk_index: 块索引
            chunk_text: 块文本
            
        Returns:
            str: 块ID
        """
        # 使用 MD5 哈希确保幂等性
        content_hash = hashlib.md5(chunk_text.encode('utf-8')).hexdigest()[:8]
        return f"{doc_id}_chunk_{chunk_index:04d}_{content_hash}"
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量
        
        对于中文，约 1.5 字符 = 1 token
        对于英文，约 4 字符 = 1 token
        
        Args:
            text: 文本
            
        Returns:
            int: 估算的 token 数量
        """
        # 统计中文字符数
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # 统计其他字符数
        other_chars = len(text) - chinese_chars
        
        # 加权估算
        return int(chinese_chars / 1.5 + other_chars / 4)


__all__ = [
    "DocumentChunk",
    "DocumentChunker"
]
