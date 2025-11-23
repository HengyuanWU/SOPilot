import logging
from typing import Dict, List, Any, TypedDict
from ..state.textbook_state import TextbookState
from ...infrastructure.llm.client import llm_call

# 配置日志
logger = logging.getLogger(__name__)


class SubchapterDict(TypedDict, total=False):
    title: str
    outline: str


class ChapterDict(TypedDict, total=False):
    title: str
    outline: str
    subchapters: List[SubchapterDict]


class Planner:
    """规划器：负责生成教材大纲与解析为结构化章节数据。"""

    def __init__(self, provider: str = "siliconflow"):
        self.provider = provider
        self.outline_prompt_template: str = (
            "你是一位专业的教材规划专家，正在为《{topic}》设计详细的教材大纲。\n\n"
            "严格按照以下要求输出：\n"
            "- 只输出 JSON 原文（不要任何说明文字、不要 Markdown 代码块```、不要前后缀）\n"
            "- 结构如下：\n"
            "{{\n"
            "  \"chapters\": [\n"
            "    {{ \"title\": \"第1章 标题\", \"outline\": \"章节概述\", \"subchapters\": [\n"
            "      {{ \"title\": \"子章节标题\", \"outline\": \"不少于30字的详细描述\" }}\n"
            "    ]}}\n"
            "  ]\n"
            "}}\n\n"
            "约束：\n"
            "1. chapters 长度为 {chapter_count}；各章包含 2-4 个子章节\n"
            "2. 所有 outline 不得为空；子章节 outline 至少 30 字\n"
            "3. 只输出 JSON（禁止使用 ```json 代码块）\n"
        )

    def generate_outline(self, topic: str, chapter_count: int = 5, language: str = "中文") -> str:
        """Generate outline using YAML-based prompt system."""
        try:
            # Use migration helper for YAML-based call
            from ...services.migration_service import migration_helper
            outline = migration_helper.call_planner(topic, chapter_count, language)
            
            if not outline or outline.strip() == "":
                raise RuntimeError(f"主题 '{topic}' 大纲生成失败（API空响应）")
            return outline
        except Exception as e:
            logger.error(f"生成大纲时出错: {e}")
            raise

    def execute(self, state: TextbookState) -> TextbookState:
        topic = state.get("topic")
        if not topic:
            raise RuntimeError("缺少必需字段: topic")
        if not state.get("chapter_count"):
            raise RuntimeError("缺少必需字段: chapter_count")
        chapter_count = state.get("chapter_count")
        language = state.get("language", "中文")

        logger.info(f"Planner 开始执行，主题: {topic}")
        logger.info(f"章节数量: {chapter_count}")

        outline = self.generate_outline(topic, chapter_count, language)
        state["outline"] = outline
        state["chapters"] = parse_outline_to_chapters(outline)
        state["planning_complete"] = True
        logger.info(f"Planner 完成，大纲长度: {len(outline)}")
        return state


def parse_outline_to_chapters(outline_text: str) -> List[Dict[str, Any]]:
    """
    将 LLM 的 JSON 输出解析为内部章节结构。
    
    现在使用 LangChain PydanticOutputParser 替代手动JSON解析。
    保持返回结构不变，确保向后兼容。
    """
    from ...infrastructure.llm.parsers import parse_textbook_outline
    return parse_textbook_outline(outline_text)

__all__ = ["Planner"]

