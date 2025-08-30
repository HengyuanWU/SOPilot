import logging
import concurrent.futures
from typing import Dict, List, Any, TypedDict
from app.domain.state.textbook_state import TextbookState
from app.infrastructure.llm.client import llm_call
from app.core.concurrency import default_concurrency_config, high_concurrency_config

logger = logging.getLogger(__name__)


class SubchapterResearch(TypedDict, total=False):
    subchapter_keywords: List[str]
    subchapter_research_summary: str
    subchapter_key_concepts: List[str]
    raw_content: str


class Researcher:
    def __init__(self, provider: str = "siliconflow"):
        self.provider = provider
        self.subchapter_prompt_template = (
            "你是一位专业的教材研究员。请仅针对给定的子章节进行研究输出。\n\n"
            "教材主题：{topic}\n"
            "子章节标题：{subchapter_title}\n"
            "子章节大纲：\n{subchapter_outline}\n\n"
            "请输出：\n"
            "1) 子章节关键词（8-12个，逗号分隔）\n"
            "2) 子章节研究总结（300-600字）\n"
            "3) 关键概念（3-6个，逗号分隔）\n\n"
            "输出格式（严格遵守）：\n"
            "## 子章节关键词\n"
            "关键词1, 关键词2, 关键词3, ...\n\n"
            "## 子章节研究总结\n"
            "[详细的研究总结]\n\n"
            "## 关键概念\n"
            "概念1, 概念2, 概念3, ...\n"
        )

    def generate_subchapter_research(self, topic: str, subchapter_title: str, subchapter_outline: str, language: str = "中文") -> SubchapterResearch:
        try:
            prompt = self.subchapter_prompt_template.format(
                topic=topic, subchapter_title=subchapter_title, subchapter_outline=subchapter_outline or "(无补充大纲)"
            )
            research_content = llm_call(prompt, api_type=self.provider, max_tokens=1500, agent_name="Researcher")
            if not research_content or research_content.strip() == "":
                raise RuntimeError(f"子章节 '{subchapter_title}' 研究内容生成失败（API空响应）")
            return self._parse_subchapter_research(research_content)
        except Exception as e:
            logger.error(f"生成子章节研究内容时出错: {e}")
            raise

    def _parse_subchapter_research(self, content: str) -> SubchapterResearch:
        subchapter_keywords: List[str] = []
        subchapter_research_summary = ""
        subchapter_key_concepts: List[str] = []
        if "## 子章节关键词" in content:
            section = content.split("## 子章节关键词")[1].split("##")[0]
            line = section.strip().split("\n")[0]
            subchapter_keywords = [kw.strip() for kw in line.split(",") if kw.strip()]
        if "## 子章节研究总结" in content:
            section = content.split("## 子章节研究总结")[1]
            subchapter_research_summary = section.strip()
        if "## 关键概念" in content:
            section = content.split("## 关键概念")[1].split("##")[0]
            line = section.strip().split("\n")[0]
            subchapter_key_concepts = [c.strip() for c in line.split(",") if c.strip()]
        return {
            "subchapter_keywords": subchapter_keywords,
            "subchapter_research_summary": subchapter_research_summary,
            "subchapter_key_concepts": subchapter_key_concepts,
            "raw_content": content,
        }

    def execute(self, state: TextbookState) -> TextbookState:
        topic = state.get("topic")
        if not topic:
            raise RuntimeError("缺少必需字段: topic")
        language = state.get("language", "中文")

        subchapter_title = state.get("subchapter_title", "").strip()
        subchapter_outline = state.get("subchapter_outline", "")
        if subchapter_title:
            logger.info(f"Researcher 子章节模式：{subchapter_title}")
            result = self.generate_subchapter_research(topic, subchapter_title, subchapter_outline, language)
            state["subchapter_keywords"] = result.get("subchapter_keywords", [])
            state["subchapter_research_summary"] = result.get("subchapter_research_summary", "")
            state["subchapter_key_concepts"] = result.get("subchapter_key_concepts", [])
            state["research_content"] = result.get("raw_content", "")
            state["research_complete"] = True
            return state

        chapters: List[Dict[str, Any]] = state.get("chapters", [])
        if chapters:
            logger.info("Researcher 并发模式：基于章节结构的子章节级研究")
            all_subchapters: List[Dict[str, str]] = []
            for chapter in chapters:
                chapter_title = chapter.get("title", "").strip()
                chapter_outline = chapter.get("outline", "")
                subchapters = chapter.get("subchapters", []) or []
                if subchapters:
                    for sub in subchapters:
                        all_subchapters.append({
                            "chapter_title": chapter_title,
                            "chapter_outline": chapter_outline,
                            "subchapter_title": sub.get("title", "").strip(),
                            "subchapter_outline": sub.get("outline", "")
                        })
                else:
                    all_subchapters.append({
                        "chapter_title": chapter_title,
                        "chapter_outline": chapter_outline,
                        "subchapter_title": chapter_title,
                        "subchapter_outline": chapter_outline
                    })

            concurrency_config = high_concurrency_config if len(all_subchapters) > 10 else default_concurrency_config
            timeout = concurrency_config.get_timeout("researcher")
            research_content_map: Dict[str, Dict[str, Any]] = {}

            def process_one(si: Dict[str, str]):
                title = si["subchapter_title"]
                outline_snippet = si["subchapter_outline"]
                res = self.generate_subchapter_research(topic, title, outline_snippet, language)
                return title, res

            with concurrency_config.create_thread_pool("researcher", len(all_subchapters)) as executor:
                futures = {executor.submit(process_one, si): si["subchapter_title"] for si in all_subchapters}
                for future in concurrent.futures.as_completed(futures):
                    title, res = future.result(timeout=timeout)
                    research_content_map[title] = res

            chapter_keywords_map: Dict[str, List[str]] = {}
            subchapter_keywords_map: Dict[str, List[str]] = {}
            all_keywords: List[str] = []
            for chapter in chapters:
                ctitle = chapter.get("title", "").strip()
                chapter_keywords: List[str] = []
                for si in all_subchapters:
                    if si["chapter_title"] == ctitle:
                        stitle = si["subchapter_title"]
                        if stitle in research_content_map:
                            kws = research_content_map[stitle].get("subchapter_keywords", [])
                            if isinstance(kws, list):
                                normalized_kws = [kw.strip() for kw in kws if kw and str(kw).strip()]
                                subchapter_keywords_map[stitle] = normalized_kws
                                chapter_keywords.extend(normalized_kws)
                                all_keywords.extend(normalized_kws)
                if not chapter_keywords:
                    chapter_keywords = [ctitle] if ctitle else []
                    all_keywords.extend(chapter_keywords)
                chapter_keywords_map[ctitle] = chapter_keywords

            import re as _re
            def _canonicalize(text: str) -> str:
                t = str(text).strip().lower()
                t = _re.sub(r"[\-_\/]+", " ", t)
                t = _re.sub(r"[^0-9a-z\u4e00-\u9fa5]+", " ", t)
                t = _re.sub(r"\s+", " ", t)
                return t.strip()

            canonical_to_original: Dict[str, str] = {}
            for kw in all_keywords:
                if not kw:
                    continue
                original = str(kw).strip()
                canonical = _canonicalize(original)
                if canonical and canonical not in canonical_to_original:
                    canonical_to_original[canonical] = original
            unique_keywords = list(canonical_to_original.values())

            state["research_content"] = research_content_map
            state["subchapter_keywords_map"] = subchapter_keywords_map
            state["chapter_keywords_map"] = chapter_keywords_map
            state["global_unique_keywords"] = unique_keywords
            state["keywords"] = unique_keywords
            state["research_complete"] = True
            return state

        raise RuntimeError("缺少子章节或章节结构：Researcher不再支持全局大纲级回退模式")

__all__ = ["Researcher"]

