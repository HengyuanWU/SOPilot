#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangChain Text Splitter - 基于 LangChain 的文本分割器

使用 LangChain 的 TextSplitter 进行文档分块，支持：
- RecursiveCharacterTextSplitter: 递归字符分割（默认）
- MarkdownTextSplitter: Markdown 文档分割
- TokenTextSplitter: 基于 token 的分割

按照 IMPROVEMENT_GUIDE.md 5.3.2 节要求实现
"""

import logging
from typing import List, Literal, Optional

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownTextSplitter,
    TokenTextSplitter,
)

logger = logging.getLogger(__name__)


def get_text_splitter(
    splitter_type: Literal["recursive", "markdown", "token"] = "recursive",
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    separators: Optional[List[str]] = None,
) -> RecursiveCharacterTextSplitter:
    """
    获取 LangChain 文本分割器
    
    Args:
        splitter_type: 分割器类型 (recursive, markdown, token)
        chunk_size: 分块大小（字符数）
        chunk_overlap: 重叠大小（字符数）
        separators: 自定义分隔符列表（仅对 recursive 有效）
        
    Returns:
        配置好的 LangChain TextSplitter 实例
        
    Examples:
        >>> splitter = get_text_splitter("recursive", chunk_size=1000)
        >>> chunks = splitter.split_text("长文本...")
    """
    if splitter_type == "recursive":
        # 默认分隔符（优先级从高到低，适合中英文混排）
        if separators is None:
            separators = [
                "\n\n",  # 段落分隔
                "\n",    # 行分隔
                "。",    # 中文句号
                "！",    # 中文感叹号
                "？",    # 中文问号
                "；",    # 中文分号
                ".",     # 英文句号
                "!",     # 英文感叹号
                "?",     # 英文问号
                ";",     # 英文分号
                " ",     # 空格
                "",      # 字符级别
            ]
        
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False,
        )
    
    elif splitter_type == "markdown":
        return MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    
    elif splitter_type == "token":
        return TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    
    else:
        raise ValueError(f"不支持的分割器类型: {splitter_type}")


def split_text_by_type(
    text: str,
    content_type: Literal["text", "markdown", "code"] = "text",
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> List[str]:
    """
    根据内容类型自动选择分割器
    
    Args:
        text: 要分割的文本
        content_type: 内容类型 (text, markdown, code)
        chunk_size: 分块大小
        chunk_overlap: 重叠大小
        
    Returns:
        分割后的文本块列表
        
    Examples:
        >>> chunks = split_text_by_type("# 标题\\n\\n内容...", "markdown")
    """
    if content_type == "markdown":
        splitter = get_text_splitter("markdown", chunk_size, chunk_overlap)
    elif content_type == "code":
        # 代码使用特殊的分隔符
        code_separators = ["\n\n", "\nclass ", "\ndef ", "\n\n\n", "\n", " ", ""]
        splitter = get_text_splitter(
            "recursive", chunk_size, chunk_overlap, separators=code_separators
        )
    else:  # text
        splitter = get_text_splitter("recursive", chunk_size, chunk_overlap)
    
    return splitter.split_text(text)


def split_documents_for_rag(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    metadata: Optional[dict] = None,
) -> List[dict]:
    """
    为 RAG 系统分割文档，返回带元数据的块
    
    Args:
        text: 要分割的文本
        chunk_size: 分块大小
        chunk_overlap: 重叠大小
        metadata: 文档元数据（会复制到每个块）
        
    Returns:
        包含 text 和 metadata 的字典列表
        
    Examples:
        >>> docs = split_documents_for_rag(
        ...     "长文本...",
        ...     metadata={"source": "book.pdf", "page": 1}
        ... )
    """
    metadata = metadata or {}
    splitter = get_text_splitter("recursive", chunk_size, chunk_overlap)
    chunks = splitter.split_text(text)
    
    return [
        {
            "text": chunk,
            "metadata": {
                **metadata,
                "chunk_index": i,
                "chunk_size": len(chunk),
            }
        }
        for i, chunk in enumerate(chunks)
    ]


# 预定义的常用配置
SPLITTER_CONFIGS = {
    "default": {"chunk_size": 800, "chunk_overlap": 120},
    "small": {"chunk_size": 400, "chunk_overlap": 60},
    "large": {"chunk_size": 1500, "chunk_overlap": 200},
    "qa": {"chunk_size": 600, "chunk_overlap": 100},  # 问答系统
    "summarization": {"chunk_size": 2000, "chunk_overlap": 100},  # 摘要生成
}


def get_splitter_by_config(config_name: str = "default") -> RecursiveCharacterTextSplitter:
    """
    根据预定义配置名称获取分割器
    
    Args:
        config_name: 配置名称 (default, small, large, qa, summarization)
        
    Returns:
        配置好的分割器
        
    Examples:
        >>> splitter = get_splitter_by_config("qa")
        >>> chunks = splitter.split_text("问答文本...")
    """
    if config_name not in SPLITTER_CONFIGS:
        logger.warning(f"未知配置 '{config_name}'，使用 'default'")
        config_name = "default"
    
    config = SPLITTER_CONFIGS[config_name]
    return get_text_splitter("recursive", **config)






