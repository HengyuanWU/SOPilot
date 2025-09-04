import logging
import re
from typing import Dict, List, Any, Tuple
from ..state.textbook_state import TextbookState
from ...infrastructure.llm.client import llm_call

logger = logging.getLogger(__name__)


class Validator:
    def __init__(self, provider: str = "siliconflow", pass_threshold: float | None = None):
        self.provider = provider
        self.pass_threshold = pass_threshold
        self.validation_prompt_template = (
            "你是一位专业的内容验证专家，正在验证《{topic}》教材的子章节「{subchapter_title}」的内容质量。\n\n"
            "子章节内容：\n{subchapter_content}\n\n"
            "子章节大纲：{subchapter_outline}\n"
            "子章节关键词：{subchapter_keywords}\n"
            "研究总结：{research_summary}\n\n"
            "请从以下四个方面进行严格验证：\n"
            "1. 内容完整性（是否覆盖大纲要求）\n"
            "2. 技术准确性（概念是否正确）\n"
            "3. 逻辑连贯性（章节间是否连贯）\n"
            "4. 语言表达（是否清晰易懂）\n\n"
            "对每个方面进行评分（1-10分），并给出具体的改进建议。\n\n"
            "输出格式：\n"
            "## 验证报告\n"
            "### 总体评分：[分数]/10\n"
            "### 详细评分：\n"
            "1. 内容完整性：[分数]/10 - [评价]\n"
            "2. 技术准确性：[分数]/10 - [评价]\n"
            "3. 逻辑连贯性：[分数]/10 - [评价]\n"
            "4. 语言表达：[分数]/10 - [评价]\n"
            "### 主要问题：[列表]\n"
            "### 改进建议：[详细建议]\n"
            "### 是否通过：[是/否]\n"
            "### 重写建议：[如果需要重写，给出具体的重写指导]"
        )

    def validate_subchapter_content(
        self,
        subchapter_title: str,
        subchapter_content: str,
        subchapter_outline: str,
        subchapter_keywords: List[str],
        research_summary: str,
        topic: str,
    ) -> Dict[str, Any]:
        keywords_str = ", ".join(subchapter_keywords) if subchapter_keywords else "无"
        prompt = self.validation_prompt_template.format(
            topic=topic,
            subchapter_title=subchapter_title,
            subchapter_content=subchapter_content[:3000],
            subchapter_outline=subchapter_outline[:500],
            subchapter_keywords=keywords_str,
            research_summary=research_summary[:500],
        )
        # Use migration helper for YAML-based call
        try:
            from ...services.migration_service import migration_helper
            validation_result = migration_helper.call_validator(
                topic=topic,
                subchapter_title=subchapter_title,
                subchapter_content=subchapter_content[:3000],
                subchapter_outline=subchapter_outline[:500],
                subchapter_keywords=keywords_str,
                research_summary=research_summary[:500]
            )
            validation_report = validation_result.get("raw_validation_content", "")
            if not validation_report or validation_report.strip() == "":
                return {
                    "subchapter_title": subchapter_title,
                    "score": 5.0,
                    "is_passed": False,
                    "report": (
                        "## 验证报告\n"
                        "### 总体评分：5/10\n"
                        "### 主要问题：验证服务不可用（空响应）\n"
                        "### 改进建议：请稍后重试验证\n"
                        "### 是否通过：否\n"
                        "### 重写建议：请等待验证服务恢复后再进行改写"
                    ),
                    "rewrite_suggestions": "",
                    "validation_time": "failed",
                    "error": "验证报告生成失败: 空响应",
                }
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                "subchapter_title": subchapter_title,
                "score": 5.0,
                "is_passed": False,
                "report": (
                    "## 验证报告\n"
                    "### 总体评分：5/10\n"
                    "### 主要问题：验证服务异常\n"
                    "### 改进建议：请稍后重试验证\n"
                    "### 是否通过：否\n"
                    "### 重写建议：请等待验证服务恢复后再进行改写"
                ),
                "rewrite_suggestions": "",
                "validation_time": "failed",
                "error": f"验证报告生成失败: {str(e)}",
            }
        score, is_passed, rewrite_suggestions = self._extract_score_from_report(
            validation_report, self._resolve_pass_threshold()
        )
        return {
            "subchapter_title": subchapter_title,
            "score": score,
            "is_passed": is_passed,
            "report": validation_report,
            "rewrite_suggestions": rewrite_suggestions,
            "validation_time": "completed",
        }

    def _resolve_pass_threshold(self) -> float:
        if self.pass_threshold is not None:
            return self.pass_threshold
        from ...core.concurrency import default_concurrency_config

        validator_cfg = default_concurrency_config.get_agent_config("validator")
        return validator_cfg.get("pass_threshold", 7.0)

    def _extract_score_from_report(self, report: str, pass_threshold: float = 7.0) -> Tuple[float, bool, str]:
        try:
            text = report or ""
            # 1) 兼容多种标题与中英文冒号、空格
            score_patterns = [
                r"(?:总体评分|总评分|评分)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*/\s*10",
                r"(\d+(?:\.\d+)?)[\s]*\/[\s]*10",  # 退级：任意 X/10
            ]
            score: float | None = None
            for pat in score_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    try:
                        score = float(m.group(1))
                        break
                    except Exception:
                        continue
            if score is None:
                score = 5.0

            # 2) 是否通过：优先解析显式“是/否”，否则用分数阈值
            pass_match = re.search(r"是否通过\s*[:：]?\s*([是否])", text)
            if pass_match:
                is_passed = pass_match.group(1) == "是"
            else:
                is_passed = score >= pass_threshold

            # 3) 重写建议：兼容不同分隔，直到下一个二级标题或结尾
            rewrite_match = re.search(r"重写建议\s*[:：]?\s*(.+?)(?=\n\s*##|\n###|\Z)", text, re.DOTALL)
            rewrite_suggestions = rewrite_match.group(1).strip() if rewrite_match else ""

            return score, is_passed, rewrite_suggestions
        except Exception:
            logger.error("提取验证报告信息失败", exc_info=True)
            return 5.0, False, "验证报告解析失败"

    def execute(self, state: TextbookState) -> TextbookState:
        subchapter_title = state.get("subchapter_title", "")
        subchapter_content = state.get("content", {}).get(subchapter_title, "")
        subchapter_outline = state.get("subchapter_outline", "")
        subchapter_keywords = state.get("subchapter_keywords", [])
        subchapter_research_summary = state.get("subchapter_research_summary", "")
        topic = state.get("topic")
        if not topic:
            raise RuntimeError("缺少必需字段: topic")
        rewrite_suggestions = state.get("rewrite_suggestions", "")
        pass_threshold = self._resolve_pass_threshold()
        if not subchapter_title:
            raise RuntimeError("缺少子章节标题，无法进行验证")
        if not subchapter_content:
            subchapter_content = f"# {subchapter_title}\n\n该子章节内容尚未生成。"
        logger.info(f"Validator 开始执行，子章节: {subchapter_title}")
        validation_result = self.validate_subchapter_content(
            subchapter_title=subchapter_title,
            subchapter_content=subchapter_content,
            subchapter_outline=subchapter_outline,
            subchapter_keywords=subchapter_keywords,
            research_summary=subchapter_research_summary,
            topic=topic,
        )
        score = validation_result["score"]
        validation_result["is_passed"] = score >= pass_threshold
        if "validation_results" not in state:
            state["validation_results"] = {}
        state["validation_results"][subchapter_title] = validation_result
        state["validation_score"] = validation_result["score"]
        state["validation_passed"] = validation_result["is_passed"]
        state["validation_report"] = validation_result["report"]
        if not validation_result["is_passed"]:
            state["needs_rewrite"] = True
            state["rewrite_suggestions"] = validation_result["rewrite_suggestions"]
            logger.warning(f"子章节 '{subchapter_title}' 验证失败，分数: {validation_result['score']}/10")
        else:
            state["needs_rewrite"] = False
            state["rewrite_suggestions"] = ""
            logger.info(f"子章节 '{subchapter_title}' 验证通过，分数: {validation_result['score']}/10")
        logger.info(f"Validator 完成，子章节: {subchapter_title}")
        return state

__all__ = ["Validator"]

