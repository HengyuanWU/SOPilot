#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
neomodel 连接初始化（按IMPROOVE_GUIDE.md规范）
"""

from __future__ import annotations

from neomodel import config

__all__ = ["init_neo4j"]


def init_neo4j(settings) -> None:
    """设置 neomodel 连接（应用启动时调用一次）。
    
    Args:
        settings: AppSettings 实例，包含 NEO4J_BOLT_URL
    """
    # neomodel 5.x: 直接设置 config.DATABASE_URL
    config.DATABASE_URL = settings.NEO4J_BOLT_URL
    # 连接参数按需可在 URL 中指定；不在代码里二次覆盖。





