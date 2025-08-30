#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any

from app.domain.agents.qa_generator import QAGenerator

logger = logging.getLogger(__name__)


def qa_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if state.get("error"):
            return state
        logger.info("执行 QA 节点")
        validation_results = state.get("validation_results", {})
        qa_results = state.get("qa_results", {})
        qa_content = state.get("qa_content", {}) or {}
        qa_metadata = state.get("qa_metadata", {}) or {}

        missing_qa = []
        for subchapter_title, validation_result in validation_results.items():
            if validation_result.get("is_passed", False) and subchapter_title not in qa_results:
                missing_qa.append(subchapter_title)

        if missing_qa:
            logger.info(f"发现 {len(missing_qa)} 个子章节需要补充 QA")
            qa_generator = QAGenerator()
            for subchapter_title in missing_qa:
                try:
                    qa_state = state.copy()
                    qa_state["current_subchapter"] = subchapter_title
                    qa_result_state = qa_generator.execute(qa_state)
                    sub_qa_results = qa_result_state.get("qa_results", {})
                    if sub_qa_results and subchapter_title in sub_qa_results:
                        qa_entry = sub_qa_results[subchapter_title]
                        text = qa_entry.get("qa_content") or qa_entry.get("content") or ""
                        meta = qa_entry.get("qa_metadata") or qa_entry.get("meta") or {}
                        if text:
                            qa_content[subchapter_title] = text
                        if meta:
                            qa_metadata[subchapter_title] = meta
                        qa_results[subchapter_title] = qa_entry
                    else:
                        text_map = qa_result_state.get("qa_content", {}) or {}
                        meta_map = qa_result_state.get("qa_metadata", {}) or {}
                        if subchapter_title in text_map:
                            qa_content[subchapter_title] = text_map[subchapter_title]
                            qa_results[subchapter_title] = {
                                "qa_content": text_map[subchapter_title],
                                "qa_metadata": meta_map.get(subchapter_title, {}),
                            }
                        if subchapter_title in meta_map:
                            qa_metadata[subchapter_title] = meta_map[subchapter_title]
                    logger.info(f"为子章节 '{subchapter_title}' 补充生成 QA")
                except Exception as e:
                    logger.error(f"为子章节 '{subchapter_title}' 生成 QA 失败: {e}")
            result_state = state.copy()
            result_state["qa_results"] = qa_results
            result_state["qa_content"] = qa_content
            result_state["qa_metadata"] = qa_metadata
        else:
            logger.info("所有通过验证的子章节都已有 QA，无需补充")
            result_state = state
        logger.info("QA 节点执行完成")
        return result_state
    except Exception as e:
        logger.error(f"QA 节点执行失败: {e}")
        error_state = state.copy()
        error_state["error"] = f"QA 生成失败: {str(e)}"
        return error_state

__all__ = ["qa_node"]

