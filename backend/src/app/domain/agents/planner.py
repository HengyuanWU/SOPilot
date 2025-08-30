import logging
from typing import Dict, List, Any, TypedDict
from app.domain.state.textbook_state import TextbookState
from app.infrastructure.llm.client import llm_call

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
        try:
            prompt = self.outline_prompt_template.format(
                topic=topic, chapter_count=chapter_count, language=language
            )
            outline = llm_call(prompt, api_type=self.provider, max_tokens=2000, agent_name="Planner")
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
    """将 LLM 的 JSON 输出解析为内部章节结构。保持返回结构不变。"""
    import json, re

    def _extract_json_candidate(text: str) -> str:
        if not isinstance(text, str):
            raise RuntimeError("规划结果类型异常（非字符串）")
        t = text.strip()
        # 优先从 ```json 或 ``` 包围中提取
        m = re.search(r"```json\s*(\{.*?\})\s*```", t, re.S | re.I)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\s*(\{.*?\})\s*```", t, re.S)
        if m:
            return m.group(1).strip()
        # 退级：寻找第一个 { 到 最后一个 } 的子串，尝试解析
        start = t.find('{')
        end = t.rfind('}')
        if start != -1 and end != -1 and end > start:
            return t[start:end+1].strip()
        # 特殊容错：仅返回了 "chapters": [...] 片段时，尝试提取 [] 并包装为对象
        idx = t.find('"chapters"')
        if idx != -1:
            # 找到 chapters 后的第一个 '['，做括号配平
            lb = t.find('[', idx)
            if lb != -1:
                depth = 0
                for i in range(lb, len(t)):
                    if t[i] == '[':
                        depth += 1
                    elif t[i] == ']':
                        depth -= 1
                        if depth == 0:
                            arr = t[lb:i+1]
                            return '{"chapters": ' + arr + '}'
        # 最终失败
        raise RuntimeError(f"未找到可解析的 JSON 片段：snippet={t[:120]!r}")

    try:
        candidate = _extract_json_candidate(outline_text)
        data = json.loads(candidate)
    except Exception as e:
        raise RuntimeError(f"规划结果非 JSON 可解析格式: {e}")

    chapters_in: List[Dict[str, Any]] = data.get("chapters") or []
    if not isinstance(chapters_in, list) or not chapters_in:
        raise RuntimeError("规划结果缺少 chapters 或为空")

    chapters: List[ChapterDict] = []
    for ch in chapters_in:
        title = (ch.get("title") or "").strip()
        outline = (ch.get("outline") or "").strip()
        subs_in = ch.get("subchapters") or []
        if not title:
            raise RuntimeError("存在章节缺少标题")
        if not outline:
            raise RuntimeError(f"章节 '{title}' 缺少 outline")
        if not isinstance(subs_in, list) or not subs_in:
            raise RuntimeError(f"章节 '{title}' 未包含任何子章节")
        subs: List[SubchapterDict] = []
        for sc in subs_in:
            stitle = (sc.get("title") or "").strip()
            soutline = (sc.get("outline") or "").strip()
            if not stitle:
                raise RuntimeError("存在子章节缺少标题")
            if len(soutline) < 30:
                raise RuntimeError(f"子章节 '{stitle}' 描述过短（需≥30字）")
            subs.append({"title": stitle, "outline": soutline})
        chapters.append({"title": title, "outline": outline, "subchapters": subs})

    return chapters

__all__ = ["Planner"]

