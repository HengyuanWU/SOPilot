#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any

from app.domain.agents.researcher import Researcher

logger = logging.getLogger(__name__)


def researcher_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if state.get("error"):
            return state
        logger.info("开始执行研究节点")
        researcher = Researcher()
        result_state = researcher.execute(state)
        logger.info("研究节点执行完成")
        return result_state
    except Exception as e:
        logger.error(f"研究节点执行失败: {e}")
        error_state = state.copy()
        error_state["error"] = f"研究失败: {str(e)}"
        return error_state

__all__ = ["researcher_node"]

