#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问答生成工作流 - 示例多工作流实现
"""

import logging
from typing import Dict, Any, List
from dataclasses import dataclass

from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


@dataclass
class QuizState:
    """问答生成工作流状态"""
    topic: str
    difficulty: str = "medium"
    question_count: int = 10
    question_types: List[str] = None
    language: str = "zh"
    
    # 生成的问答
    questions: List[Dict[str, Any]] = None
    formatted_output: str = None
    
    # 状态追踪
    current_stage: str = "start"
    error_message: str = None
    

def get_metadata():
    """
    获取问答生成工作流元数据
    
    Returns:
        工作流元数据字典
    """
    return {
        "id": "quiz_maker",
        "name": "问答生成器",
        "description": "基于指定主题快速生成多种类型的问答题目，支持选择题、填空题、简答题等格式",
        "version": "1.0.0",
        "tags": ["quiz", "questions", "assessment", "education"],
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "title": "问答主题",
                    "description": "请输入问答题目的主题，例如：'Python基础语法'、'数据结构与算法'等",
                    "minLength": 2,
                    "maxLength": 100
                },
                "difficulty": {
                    "type": "string",
                    "title": "难度级别",
                    "description": "选择问答题目的难度级别",
                    "enum": ["easy", "medium", "hard"],
                    "default": "medium"
                },
                "question_count": {
                    "type": "integer",
                    "title": "题目数量",
                    "description": "要生成的问答题目数量",
                    "minimum": 5,
                    "maximum": 50,
                    "default": 10
                },
                "question_types": {
                    "type": "array",
                    "title": "题目类型",
                    "description": "选择要生成的问答题目类型",
                    "items": {
                        "type": "string",
                        "enum": ["multiple_choice", "true_false", "fill_blank", "short_answer"]
                    },
                    "default": ["multiple_choice", "short_answer"],
                    "minItems": 1
                },
                "language": {
                    "type": "string",
                    "title": "语言",
                    "description": "问答生成语言",
                    "enum": ["zh", "en"],
                    "default": "zh"
                }
            },
            "required": ["topic"],
            "additionalProperties": False
        },
        "ui_schema": {
            "topic": {
                "ui:widget": "textarea",
                "ui:placeholder": "例如：Python基础语法、数据结构与算法..."
            },
            "difficulty": {
                "ui:widget": "select"
            },
            "question_count": {
                "ui:widget": "updown"
            },
            "question_types": {
                "ui:widget": "checkboxes"
            },
            "language": {
                "ui:widget": "radio"
            }
        }
    }


def question_generator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    问题生成节点 - 生成问答题目
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的状态
    """
    try:
        # 模拟问题生成（实际应调用LLM）
        logger.info(f"Generating {state.get('question_count', 10)} questions for topic: {state.get('topic')}")
        
        # 这里应该调用LLM服务生成真实的问答题目
        # 为演示目的，我们创建示例问题
        questions = []
        topic = state.get('topic', '示例主题')
        question_count = state.get('question_count', 10)
        question_types = state.get('question_types', ['multiple_choice', 'short_answer'])
        
        for i in range(question_count):
            question_type = question_types[i % len(question_types)]
            
            if question_type == 'multiple_choice':
                question = {
                    "id": i + 1,
                    "type": "multiple_choice",
                    "question": f"关于{topic}的第{i+1}个选择题？",
                    "options": ["选项A", "选项B", "选项C", "选项D"],
                    "correct_answer": "A",
                    "explanation": f"这是关于{topic}的解释"
                }
            elif question_type == 'short_answer':
                question = {
                    "id": i + 1,
                    "type": "short_answer",
                    "question": f"请简述{topic}的第{i+1}个概念？",
                    "sample_answer": f"这是关于{topic}的简答题参考答案",
                    "keywords": [f"关键词{i+1}", f"概念{i+1}"]
                }
            else:
                question = {
                    "id": i + 1,
                    "type": question_type,
                    "question": f"关于{topic}的第{i+1}个{question_type}题目？",
                    "answer": "示例答案"
                }
                
            questions.append(question)
        
        return {
            **state,
            "questions": questions,
            "current_stage": "questions_generated"
        }
        
    except Exception as e:
        logger.error(f"Error in question generation: {e}")
        return {
            **state,
            "error_message": str(e),
            "current_stage": "error"
        }


def formatter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    格式化节点 - 将生成的问题格式化为最终输出
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的状态
    """
    try:
        questions = state.get('questions', [])
        topic = state.get('topic', '问答题目')
        
        # 格式化输出
        formatted_lines = [
            f"# {topic} - 问答题目",
            "",
            f"**总计题目数量**: {len(questions)}",
            f"**难度级别**: {state.get('difficulty', 'medium')}",
            f"**生成语言**: {state.get('language', 'zh')}",
            "",
            "---",
            ""
        ]
        
        for i, question in enumerate(questions, 1):
            formatted_lines.append(f"## 题目 {i}")
            formatted_lines.append("")
            formatted_lines.append(f"**类型**: {question.get('type', '未知')}")
            formatted_lines.append(f"**题目**: {question.get('question', '')}")
            
            if question.get('type') == 'multiple_choice':
                for j, option in enumerate(question.get('options', []), 1):
                    letter = chr(64 + j)  # A, B, C, D
                    formatted_lines.append(f"{letter}. {option}")
                formatted_lines.append(f"**正确答案**: {question.get('correct_answer', '')}")
                if question.get('explanation'):
                    formatted_lines.append(f"**解释**: {question.get('explanation', '')}")
            elif question.get('type') == 'short_answer':
                if question.get('sample_answer'):
                    formatted_lines.append(f"**参考答案**: {question.get('sample_answer', '')}")
                if question.get('keywords'):
                    formatted_lines.append(f"**关键词**: {', '.join(question.get('keywords', []))}")
            else:
                if question.get('answer'):
                    formatted_lines.append(f"**答案**: {question.get('answer', '')}")
            
            formatted_lines.append("")
            formatted_lines.append("---")
            formatted_lines.append("")
        
        formatted_output = "\n".join(formatted_lines)
        
        return {
            **state,
            "formatted_output": formatted_output,
            "current_stage": "completed"
        }
        
    except Exception as e:
        logger.error(f"Error in formatting: {e}")
        return {
            **state,
            "error_message": str(e),
            "current_stage": "error"
        }


class QuizMakerWorkflow:
    """问答生成工作流"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.app = None
        self._build_graph()
    
    def _build_graph(self):
        """构建工作流图"""
        workflow = StateGraph(dict)  # 使用字典作为状态类型
        
        # 添加节点
        workflow.add_node("question_generator", question_generator_node)
        workflow.add_node("formatter", formatter_node)
        
        # 设置入口点
        workflow.set_entry_point("question_generator")
        
        # 添加边
        workflow.add_edge("question_generator", "formatter")
        
        # 设置结束点
        workflow.set_finish_point("formatter")
        
        # 编译工作流
        self.app = workflow.compile(checkpointer=MemorySaver())
    
    def execute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工作流
        
        Args:
            initial_state: 初始状态
            
        Returns:
            执行结果
        """
        try:
            import uuid as _uuid
            thread_id = initial_state.get("thread_id", str(_uuid.uuid4()))
            config = {"configurable": {"thread_id": thread_id}}
            
            # 清理状态，移除不需要的字段
            safe_state = initial_state.copy()
            if "vector_store" in safe_state:
                del safe_state["vector_store"]
            
            # 执行工作流
            result = self.app.invoke(safe_state, config=config)
            return result
            
        except Exception as e:
            logger.error(f"Error executing quiz maker workflow: {e}")
            return {
                **initial_state,
                "error_message": str(e),
                "current_stage": "error"
            }


def get_workflow():
    """
    获取问答生成工作流实例
    
    Returns:
        QuizMakerWorkflow实例
    """
    return QuizMakerWorkflow()