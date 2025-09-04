#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any

from ..merger import Merger

logger = logging.getLogger(__name__)


def merger_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if state.get("error"):
            return state
        logger.info("开始执行合并节点")
        merger = Merger()
        result_state = merger.execute(state)
        logger.info("合并节点执行完成")
        return result_state
    except Exception as e:
        logger.error(f"合并节点执行失败: {e}")
        error_state = state.copy()
        error_state["error"] = f"合并失败: {str(e)}"
        return error_state

__all__ = ["merger_node"]

