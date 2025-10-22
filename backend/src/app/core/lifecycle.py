#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用生命周期管理
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from ..core.settings import get_settings
from ..infrastructure.graph_store.neomodel_conn import init_neo4j
from ..infrastructure.graph_store.schema import install_schema

logger = logging.getLogger(__name__)


def register_lifecycle(app: FastAPI) -> None:
    """注册应用生命周期钩子。"""

    @app.on_event("startup")
    async def on_startup() -> None:  # noqa: F811
        """应用启动时执行。"""
        try:
            # 获取设置
            settings = get_settings()

            # 初始化Neo4j连接
            logger.info("初始化Neo4j连接...")
            init_neo4j(settings)

            # 安装Schema（约束和索引）
            logger.info("安装Neo4j Schema...")
            install_schema()

            logger.info("Neo4j初始化完成")
        except Exception as e:
            logger.exception(f"Neo4j初始化失败: {e}")
            # 不阻塞应用启动，但记录错误
            # raise

    @app.on_event("shutdown")
    async def on_shutdown() -> None:  # noqa: F811
        """应用关闭时执行。"""
        logger.info("应用正在关闭...")

