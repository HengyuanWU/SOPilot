#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG ID 生成与规范化工具（域层）
"""

import hashlib
import re
from typing import Optional


def generate_section_id(topic: str, chapter: str, subchapter: str) -> str:
    content = f"{topic}|{chapter or ''}|{subchapter or ''}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]


def generate_content_hash(content: str) -> str:
    normalized = re.sub(r'\s+', ' ', content.strip())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:12]


def slug(text: str) -> str:
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]+', '_', text)
    return cleaned.strip('_').lower()


def generate_concept_id(name: str, topic: str, chapter: str, subchapter: str) -> str:
    slug_name = slug(name)
    content = f"{topic}|{chapter or ''}|{subchapter or ''}"
    hash_suffix = hashlib.md5(content.encode('utf-8')).hexdigest()[:6]
    return f"concept:{slug_name}:{hash_suffix}"


def generate_chapter_id(chapter_name: str, doc_id: str) -> str:
    slug_name = slug(chapter_name)
    content = f"{doc_id}|{chapter_name}"
    hash_suffix = hashlib.md5(content.encode('utf-8')).hexdigest()[:6]
    return f"chapter:{slug_name}:{hash_suffix}"


def generate_subchapter_id(subchapter_name: str, doc_id: str, chapter_name: str) -> str:
    slug_name = slug(subchapter_name)
    content = f"{doc_id}|{chapter_name}|{subchapter_name}"
    hash_suffix = hashlib.md5(content.encode('utf-8')).hexdigest()[:6]
    return f"subchapter:{slug_name}:{hash_suffix}"


def generate_book_id(topic: str, language: str = "zh") -> str:
    """
    生成整本书的唯一标识符（严格按 IMPROOVE_GUIDE.md 要求）。
    
    格式：book:{slug(topic)}:{md5(topic)[:8]}
    
    Args:
        topic: 教材主题
        language: 语言代码 (默认 "zh")
        
    Returns:
        格式为 "book:{slug_topic}:{md5_hash}" 的字符串
    
    示例:
        >>> generate_book_id("测试", "zh")
        'book:测试:864d5654'
    """
    if not topic:
        import time
        return f"book:unknown:{int(time.time() * 1000)}"
    
    topic_slug = slug(topic)
    hash_suffix = hashlib.md5(topic.encode("utf-8")).hexdigest()[:8]
    
    return f"book:{topic_slug}:{hash_suffix}"


def generate_relation_rid(edge_type: str, source_id: str, target_id: str, scope: str) -> str:
    """
    生成关系的唯一标识符。
    
    Args:
        edge_type: 关系类型
        source_id: 源节点ID
        target_id: 目标节点ID
        scope: 范围标识 (如 "section:xxx" 或 "book:xxx")
        
    Returns:
        16位MD5哈希字符串
    """
    raw = f"{edge_type}|{source_id}|{target_id}|{scope}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

