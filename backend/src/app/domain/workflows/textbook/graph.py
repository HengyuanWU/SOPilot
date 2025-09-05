#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
教材生成工作流（迁移版，引用现有节点实现）
"""

import logging
from typing import Dict, Any

from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

from ...state.textbook_state import TextbookState
from .nodes.planner_node import planner_node
from .nodes.researcher_node import researcher_node
from .nodes.writer_node import writer_node
from .nodes.qa_node import qa_node
from .nodes.kg_node import kg_node
from .nodes.book_graph_node import book_graph_node
from .nodes.merger_node import merger_node
from ....core.progress_manager import progress_manager

logger = logging.getLogger(__name__)


def get_metadata():
    """
    获取教材生成工作流元数据
    
    Returns:
        工作流元数据字典
    """
    return {
        "id": "textbook",
        "name": "教材生成",
        "description": "基于主题生成完整的教材内容，包括章节规划、内容研究、写作、QA生成和知识图谱构建",
        "version": "1.0.0",
        "tags": ["education", "textbook", "ai-generated"],
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "title": "教材主题",
                    "description": "请输入要生成教材的主题，例如：'机器学习基础'、'Python编程入门'等",
                    "minLength": 2,
                    "maxLength": 200
                },
                "target_audience": {
                    "type": "string", 
                    "title": "目标受众",
                    "description": "教材的目标读者群体",
                    "enum": ["初学者", "中级", "高级", "专业人士"],
                    "default": "初学者"
                },
                "language": {
                    "type": "string",
                    "title": "语言",
                    "description": "教材生成语言",
                    "enum": ["zh", "en"],
                    "default": "zh"
                },
                "chapter_count": {
                    "type": "integer",
                    "title": "章节数量",
                    "description": "期望生成的章节数量",
                    "minimum": 3,
                    "maximum": 15,
                    "default": 3
                },
                "enable_qa": {
                    "type": "boolean",
                    "title": "生成问答",
                    "description": "是否为每个章节生成配套的问答题目",
                    "default": True
                },
                "enable_kg": {
                    "type": "boolean", 
                    "title": "构建知识图谱",
                    "description": "是否构建教材的知识图谱",
                    "default": True
                }
            },
            "required": ["topic"],
            "additionalProperties": False
        },
        "ui_schema": {
            "topic": {
                "ui:widget": "textarea",
                "ui:placeholder": "例如：机器学习基础、Python编程入门..."
            },
            "target_audience": {
                "ui:widget": "select"
            },
            "language": {
                "ui:widget": "radio"
            },
            "chapter_count": {
                "ui:widget": "updown"
            },
            "enable_qa": {
                "ui:widget": "checkbox"
            },
            "enable_kg": {
                "ui:widget": "checkbox"
            }
        }
    }


def get_workflow():
    """
    获取教材生成工作流实例
    
    Returns:
        TextbookWorkflow实例
    """
    return TextbookWorkflow()


class TextbookWorkflow:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.app = None
        self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(TextbookState)

        stage_descriptions = {
            "planner": "生成教材大纲",
            "researcher": "并发研究子章节，生成关键词与摘要",
            "writer": "并发写作与验证，验证通过即生成QA",
            "qa_generator": "补齐缺失的QA（如有）",
            "kg_builder": "为通过验证的子章节构建知识图谱",
            "book_graph": "构建整本书知识图谱视图",
            "merger": "编排并合成最终教材",
        }

        def wrap(node_name, func):
            def _wrapped(state: Dict[str, Any]) -> Dict[str, Any]:
                progress_started = False
                try:
                    progress_manager.start_stage(node_name, stage_descriptions.get(node_name, ""))
                    progress_started = True
                    return func(state)
                finally:
                    if progress_started:
                        try:
                            progress_manager.end_stage()
                        except Exception:
                            pass

            return _wrapped

        workflow.add_node("planner", wrap("planner", planner_node))
        workflow.add_node("researcher", wrap("researcher", researcher_node))
        workflow.add_node("writer", wrap("writer", writer_node))
        workflow.add_node("qa_generator", wrap("qa_generator", qa_node))
        workflow.add_node("kg_builder", wrap("kg_builder", kg_node))
        workflow.add_node("book_graph", wrap("book_graph", book_graph_node))
        workflow.add_node("merger", wrap("merger", merger_node))

        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "researcher")
        workflow.add_edge("researcher", "writer")
        workflow.add_edge("writer", "qa_generator")
        workflow.add_edge("qa_generator", "kg_builder")
        workflow.add_edge("kg_builder", "book_graph")
        workflow.add_edge("book_graph", "merger")
        workflow.set_finish_point("merger")

        self.app = workflow.compile(checkpointer=MemorySaver())

    def execute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            progress_manager.start_workflow(total_stages=7)
            import uuid as _uuid
            thread_id = initial_state.get("thread_id", str(_uuid.uuid4()))
            config = {"configurable": {"thread_id": thread_id}}
            safe_state = initial_state.copy()
            if "vector_store" in safe_state:
                del safe_state["vector_store"]
            result = self.app.invoke(safe_state, config=config)
            return result
        finally:
            try:
                progress_manager.end_workflow()
            except Exception:
                pass

