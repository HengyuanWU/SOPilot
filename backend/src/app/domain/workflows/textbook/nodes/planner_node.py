#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规划节点 - 轻薄编排层（域层实现）
"""

import logging
from typing import Dict, Any

from app.domain.agents.planner import Planner

logger = logging.getLogger(__name__)


def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        logger.info("开始执行规划节点")
        planner = Planner()
        result_state = planner.execute(state)
        logger.info("规划节点执行完成")
        return result_state
    except Exception as e:
        logger.error(f"规划节点执行失败: {e}")
        error_state = state.copy()
        error_state["error"] = f"规划失败: {str(e)}"
        return error_state

__all__ = ["planner_node"]

