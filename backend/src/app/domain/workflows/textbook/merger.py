#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
教材工作流 Merger（域层，位于 workflows/textbook）
职责：汇总 Planner/Researcher/Writer/QA/KG 的产出，生成最终 Markdown 教材文本。
"""

from __future__ import annotations

from typing import Dict, Any, List


class Merger:
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        result_state = state.copy()

        chapters: List[Dict[str, Any]] = state.get("chapters", []) or []
        content_map: Dict[str, str] = state.get("content", {}) or {}
        qa_map: Dict[str, str] = state.get("qa_content", {}) or {}
        qa_meta_map: Dict[str, Any] = state.get("qa_metadata", {}) or {}

        # 可选：KG 概览（来自 evaluator/cross_agent_insights）
        insights = (state.get("cross_agent_insights", {}) or {}).get("kg_builder", {}) or {}
        kg_summary = insights.get("kg_summary")
        kg_structure = insights.get("kg_structure", {})

        lines: List[str] = []

        # 逐章编排
        for chapter in chapters:
            chapter_title = chapter.get("title") or "章节"
            chapter_outline = chapter.get("outline") or ""
            lines.append(f"# {chapter_title}")
            if chapter_outline:
                lines.append(f"> {chapter_outline}")

            for sub in chapter.get("subchapters", []) or []:
                stitle = sub.get("title") or "小节"
                soutline = (sub.get("outline") or "").strip()
                lines.append(f"## {stitle}")
                if soutline:
                    lines.append(f"_导学：{soutline}_")

                body = (content_map.get(stitle) or "").strip()
                if body:
                    lines.append(body)
                else:
                    lines.append("> [内容缺失]")

                # QA（如有）
                qa_text = (qa_map.get(stitle) or "").strip()
                if qa_text:
                    lines.append("\n### 问答")
                    lines.append(qa_text)

        # 附录：知识图谱摘要（如有）
        appendix: List[str] = []
        if kg_summary or kg_structure:
            appendix.append("# 附录：知识图谱概览")
            if kg_summary:
                appendix.append(kg_summary)
            if isinstance(kg_structure, dict) and kg_structure:
                total_nodes = kg_structure.get("total_nodes")
                total_edges = kg_structure.get("total_edges")
                if total_nodes is not None and total_edges is not None:
                    appendix.append(f"- 图节点数：{total_nodes}")
                    appendix.append(f"- 图边数量：{total_edges}")
        if appendix:
            lines.append("\n\n".join(appendix))

        result_state["final_content"] = "\n\n".join(lines).strip()
        return result_state


__all__ = ["Merger"]