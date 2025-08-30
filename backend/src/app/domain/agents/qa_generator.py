import logging
from typing import Dict, List, Any
from app.domain.state.textbook_state import TextbookState
from app.infrastructure.llm.client import llm_call

logger = logging.getLogger(__name__)


class QAGenerator:
    def __init__(self, provider: str = "siliconflow"):
        self.provider = provider
        self.qa_prompt_template = (
            "你是一位专业的面试官，正在为《{topic}》教材的子章节「{subchapter_title}」生成面试问答。\n\n"
            "子章节内容：\n{subchapter_content}\n\n"
            "子章节关键词：{subchapter_keywords}\n"
            "研究总结：{research_summary}\n\n"
            "请为该子章节生成5-8个高质量的面试问答，包括：\n"
            "1. 基础概念问答（2-3个）：测试对核心概念的理解\n"
            "2. 技术实现问答（2-3个）：测试实际应用能力\n"
            "3. 深度思考问答（1-2个）：测试分析和解决问题的能力\n\n"
            "每个问答要求：\n"
            "- 问题清晰明确，有针对性\n"
            "- 答案详细准确，包含关键要点\n"
            "- 难度适中，符合学习进度\n"
            "- 与子章节内容紧密相关\n\n"
            "输出格式：\n"
            "### Q1: [问题]\n"
            "**A:** [详细答案]\n"
            "**难度:** [初级/中级/高级]\n"
            "**类型:** [概念/技术/应用]\n"
            "**关键词:** [相关概念标签]\n\n"
            "### Q2: [问题]\n"
            "**A:** [详细答案]\n"
            "**难度:** [初级/中级/高级]\n"
            "**类型:** [概念/技术/应用]\n"
            "**关键词:** [相关概念标签]\n\n"
            "请确保问答质量高，内容准确，适合{language}教学环境。"
        )

    def generate_subchapter_qa(
        self,
        subchapter_title: str,
        subchapter_content: str,
        subchapter_keywords: List[str],
        research_summary: str,
        topic: str,
        language: str,
    ) -> Dict[str, Any]:
        keywords_str = ", ".join(subchapter_keywords) if subchapter_keywords else "无"
        prompt = self.qa_prompt_template.format(
            topic=topic,
            subchapter_title=subchapter_title,
            subchapter_content=subchapter_content[:2000],
            subchapter_keywords=keywords_str,
            research_summary=research_summary[:500],
            language=language,
        )
        qa_content = llm_call(prompt, api_type=self.provider, max_tokens=2500, agent_name="QAGenerator")
        if not qa_content or qa_content.strip() == "":
            raise RuntimeError(f"子章节 '{subchapter_title}' 问答生成失败（API空响应）")
        qa_count = qa_content.count("### Q")
        return {
            "subchapter_title": subchapter_title,
            "qa_content": qa_content,
            "qa_count": qa_count,
            "keywords": subchapter_keywords,
            "generation_time": "completed",
        }

    def execute(self, state: TextbookState) -> TextbookState:
        subchapter_title = state.get("subchapter_title", "")
        subchapter_content = state.get("content", {}).get(subchapter_title, "")
        subchapter_keywords = state.get("subchapter_keywords", [])
        subchapter_research_summary = state.get("subchapter_research_summary", "")
        topic = state.get("topic")
        if not topic:
            raise RuntimeError("缺少必需字段: topic")
        language = state.get("language", "中文")
        if not subchapter_title:
            raise RuntimeError("缺少子章节标题，无法生成问答")
        if not subchapter_content:
            raise RuntimeError(f"缺少子章节 '{subchapter_title}' 内容，无法生成问答")
        logger.info(f"QAGenerator 开始执行，子章节: {subchapter_title}")
        qa_result = self.generate_subchapter_qa(
            subchapter_title=subchapter_title,
            subchapter_content=subchapter_content,
            subchapter_keywords=subchapter_keywords,
            research_summary=subchapter_research_summary,
            topic=topic,
            language=language,
        )
        if "qa_content" not in state:
            state["qa_content"] = {}
        state["qa_content"][subchapter_title] = qa_result["qa_content"]
        if "qa_metadata" not in state:
            state["qa_metadata"] = {}
        state["qa_metadata"][subchapter_title] = {
            "qa_count": qa_result["qa_count"],
            "keywords": qa_result["keywords"],
            "generation_time": qa_result["generation_time"],
            "error": qa_result.get("error", None),
        }
        state["interview_qa"] = qa_result["qa_content"]
        logger.info(f"QAGenerator 完成，子章节: {subchapter_title}")
        logger.info(f"生成问答数量: {qa_result['qa_count']}")
        return state

__all__ = ["QAGenerator"]

