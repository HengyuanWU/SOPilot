#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j neomodel 模型定义（按IMPROOVE_GUIDE.md规范）
"""

from __future__ import annotations

from datetime import datetime

from neomodel import (
    ArrayProperty,
    DateTimeProperty,
    FloatProperty,
    StringProperty,
    StructuredNode,
    StructuredRel,
)

__all__ = [
    "KGRel",
    "BaseEntity",
    "Concept",
    "Chapter",
    "Subchapter",
    "Method",
    "Example",
    "Dataset",
    "Equation",
    "Doc",
    "Chunk",
]


# —— 关系属性：固定最小集合；可选 evidence 便于溯源 ——
class KGRel(StructuredRel):
    """知识图谱关系属性。"""

    rid = StringProperty(required=True)  # 关系唯一键（由 pipeline 计算）
    type = StringProperty(required=True)  # 关系类型（与边类型一致）
    src = StringProperty(required=True)  # 小节级来源 section_id
    scope = StringProperty(required=True)  # section_id 或 book_id
    confidence = FloatProperty(default=1.0)
    weight = FloatProperty(default=1.0)
    created_at = DateTimeProperty(default_now=True)
    evidence = StringProperty()  # 选填：对齐的 chunk_id


# —— 节点公共基类 ——
class BaseEntity(StructuredNode):
    """知识图谱节点基类。"""

    id = StringProperty(required=True, unique_index=True)  # 全局唯一
    name = StringProperty(required=True)
    type = StringProperty(required=True)  # 固定为标签名
    desc = StringProperty()  # ≤ 2KB，外部保证截断
    aliases = ArrayProperty()
    scope = StringProperty()  # 可留空；用于 Doc/Chunk
    created_at = DateTimeProperty(default_now=True)
    updated_at = DateTimeProperty(default_now=True)

    def touch(self):
        """更新 updated_at 时间戳。"""
        self.updated_at = datetime.utcnow()
        self.save()


# —— 9 类节点（标签名 = 类名）——
class Concept(BaseEntity):
    """概念节点。"""

    pass


class Chapter(BaseEntity):
    """章节点。"""

    pass


class Subchapter(BaseEntity):
    """小节节点。"""

    pass


class Method(BaseEntity):
    """方法节点。"""

    pass


class Example(BaseEntity):
    """示例节点。"""

    pass


class Dataset(BaseEntity):
    """数据集节点。"""

    pass


class Equation(BaseEntity):
    """公式节点。"""

    pass


class Doc(BaseEntity):
    """文档节点。"""

    pass


class Chunk(BaseEntity):
    """文本块节点。"""

    pass










