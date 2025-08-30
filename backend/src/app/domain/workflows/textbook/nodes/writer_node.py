#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.domain.agents.writer import Writer
from app.domain.agents.validator import Validator
from app.domain.agents.qa_generator import QAGenerator
from app.core.concurrency import get_concurrency_config

logger = logging.getLogger(__name__)


def writer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if state.get("error"):
            return state
        logger.info("开始执行写作节点")
        concurrency_config = get_concurrency_config()
        max_workers = concurrency_config["writer"]["max_workers"]
        max_rewrite_attempts = concurrency_config["validator"]["max_rewrite_attempts"]

        chapters = state.get("chapters", [])
        if not chapters:
            logger.warning("没有找到章节信息")
            return state

        all_subchapters = []
        for chapter in chapters:
            chapter_title = chapter["title"]
            for subchapter in chapter.get("subchapters", []):
                all_subchapters.append((chapter_title, subchapter))

        if not all_subchapters:
            logger.warning("没有找到子章节")
            return state

        content = {}
        validation_results = {}
        qa_content = {}
        qa_metadata = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_subchapter = {
                executor.submit(
                    process_subchapter_with_validation,
                    chapter_title,
                    subchapter,
                    state,
                    max_rewrite_attempts,
                ): (chapter_title, subchapter)
                for chapter_title, subchapter in all_subchapters
            }

            for future in as_completed(future_to_subchapter):
                chapter_title, subchapter = future_to_subchapter[future]
                subchapter_title = subchapter["title"]
                try:
                    subchapter_content, validation_result, qa_result = future.result()
                    content[subchapter_title] = subchapter_content
                    validation_results[subchapter_title] = validation_result
                    if qa_result:
                        if isinstance(qa_result, dict):
                            text = qa_result.get("qa_content") or qa_result.get("content") or ""
                            meta = qa_result.get("qa_metadata") or qa_result.get("meta") or {}
                        else:
                            text, meta = str(qa_result), {}
                        if text:
                            qa_content[subchapter_title] = text
                        if meta:
                            qa_metadata[subchapter_title] = meta
                    logger.info(f"子章节 '{subchapter_title}' 处理完成")
                except Exception as e:
                    logger.error(f"子章节 '{subchapter_title}' 处理失败: {e}")
                    content[subchapter_title] = f"内容生成失败: {str(e)}"
                    validation_results[subchapter_title] = {
                        "is_passed": False,
                        "score": 0.0,
                        "suggestions": f"处理失败: {str(e)}",
                    }

        result_state = state.copy()
        result_state["content"] = content
        result_state["validation_results"] = validation_results
        result_state["qa_content"] = qa_content
        result_state["qa_metadata"] = qa_metadata
        result_state["qa_results"] = {
            k: {"qa_content": qa_content.get(k, ""), "qa_metadata": qa_metadata.get(k, {})}
            for k in set(list(qa_content.keys()) + list(qa_metadata.keys()))
        }

        # 统计写入，便于下游/结果诊断
        try:
            total = len(all_subchapters)
            passed = sum(1 for v in validation_results.values() if v.get("is_passed", False))
            stats = result_state.get("processing_stats", {}) or {}
            stats["writer"] = {"total_subchapters": total, "passed_subchapters": passed}
            result_state["processing_stats"] = stats
        except Exception:
            pass

        logger.info(f"写作节点执行完成，处理了 {len(all_subchapters)} 个子章节")
        return result_state
    except Exception as e:
        logger.error(f"写作节点执行失败: {e}")
        error_state = state.copy()
        error_state["error"] = f"写作失败: {str(e)}"
        return error_state


def process_subchapter_with_validation(
    chapter_title: str, subchapter: Dict[str, Any], state: Dict[str, Any], max_rewrite_attempts: int
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    subchapter_title = subchapter["title"]
    subchapter_outline = subchapter.get("outline", "")
    try:
        writer = Writer()
        validator = Validator()
        qa_generator = QAGenerator()

        subchapter_state = state.copy()
        subchapter_state["subchapter_title"] = subchapter_title
        subchapter_state["chapter_title"] = chapter_title
        subchapter_state["subchapter_outline"] = subchapter_outline
        sk_map = state.get("subchapter_keywords_map", {}) or {}
        sub_research_map = state.get("research_content", {}) or {}
        if isinstance(sk_map, dict):
            subchapter_state["subchapter_keywords"] = sk_map.get(subchapter_title, [])
        if isinstance(sub_research_map, dict):
            subchapter_state["subchapter_research_summary"] = (
                sub_research_map.get(subchapter_title, {}) or {}
            ).get("subchapter_research_summary", "")

        current_content = ""
        validation_result = {"is_passed": False, "score": 0.0, "suggestions": ""}
        for attempt in range(max_rewrite_attempts + 1):
            writer_state = writer.execute(subchapter_state)
            current_content = writer_state.get("content", {}).get(subchapter_title, "")
            validation_state = subchapter_state.copy()
            validation_state["content"] = {subchapter_title: current_content}
            validator_state = validator.execute(validation_state)
            validation_result = (
                validator_state.get("validation_results", {}).get(subchapter_title, {})
            )
            if validation_result.get("is_passed", False):
                logger.info(f"子章节 '{subchapter_title}' 第 {attempt + 1} 次尝试通过验证")
                break
            subchapter_state["rewrite_suggestions"] = validation_result.get("suggestions", "")

        qa_result = {}
        if validation_result.get("is_passed", False):
            try:
                qa_state = subchapter_state.copy()
                qa_state["content"] = {subchapter_title: current_content}
                qa_state_result = qa_generator.execute(qa_state)
                qa_text_map = qa_state_result.get("qa_content", {})
                qa_meta_map = qa_state_result.get("qa_metadata", {})
                qa_result = {
                    "qa_content": qa_text_map.get(subchapter_title, ""),
                    "qa_metadata": qa_meta_map.get(subchapter_title, {}),
                }
                logger.info(f"子章节 '{subchapter_title}' QA 生成完成")
            except Exception as e:
                logger.error(f"子章节 '{subchapter_title}' QA 生成失败: {e}")
        return current_content, validation_result, qa_result
    except Exception as e:
        logger.error(f"处理子章节 '{subchapter_title}' 失败: {e}")
        return (
            f"处理失败: {str(e)}",
            {"is_passed": False, "score": 0.0, "suggestions": str(e)},
            {},
        )

__all__ = ["writer_node"]

