import logging
from typing import Dict, List, Any
from ..state.textbook_state import TextbookState
from ...infrastructure.llm.client import llm_call

logger = logging.getLogger(__name__)


class Writer:
    """编写器：负责生成子章节内容"""

    def __init__(self, provider: str = "siliconflow"):
        self.provider = provider
        self.writer_prompt_template = (
            "你是一位专业的教材编写专家，正在为《{topic}》教材编写子章节内容。\n\n"
            "当前任务：编写子章节「{subchapter_title}」的完整内容\n\n"
            "子章节大纲：{subchapter_outline}\n"
            "子章节关键词：{subchapter_keywords}\n"
            "研究总结：{research_summary}\n"
            "{rewrite_instructions}\n\n"
            "写作要求：\n"
            "1. **子章节概述**（200-300字）：\n"
            "   - 本子章节的学习目标和重要性\n"
            "   - 在{chapter_title}中的作用和地位\n"
            "   - 与{chapter_title}其他部分的关联关系\n\n"
            "2. **核心内容**（800-1200字）：\n"
            "   - 按照大纲结构展开详细内容\n"
            "   - 重点围绕关键词进行深入讲解\n"
            "   - 包含理论原理和实际应用\n"
            "   - 确保每个关键词都有对应的内容解释\n\n"
            "3. **技术实现**（400-600字）：\n"
            "   - 提供具体的实现方法和步骤\n"
            "   - 包含关键代码片段和示例\n"
            "   - 说明实现中的注意事项和最佳实践\n\n"
            "4. **实践指导**（300-400字）：\n"
            "   - 具体的实践步骤和操作指南\n"
            "   - 常见问题和解决方案\n"
            "   - 学习建议和注意事项\n\n"
            "写作风格：\n"
            "- 语言生动有趣，避免死板的教学语言\n"
            "- 内容必须紧扣{chapter_title}主题，避免偏离\n"
            "- 结构清晰，逻辑性强\n"
            "- 适合{language}教学环境\n"
            "- 确保关键词在上下文中含义明确，避免歧义\n\n"
            "请为子章节「{subchapter_title}」撰写专业、系统、实用的教材内容。"
        )

    def _enhance_writing_with_rag(self, topic: str, subchapter_title: str, subchapter_keywords: List[str], research_summary: str) -> str:
        """使用RAG增强写作内容"""
        try:
            from ...services.rag_service import rag_service
            
            # 构建查询：结合主题、子章节标题和关键词
            query_parts = [topic, subchapter_title]
            if subchapter_keywords:
                query_parts.extend(subchapter_keywords[:3])  # 只取前3个关键词
            query = " ".join(query_parts)
            
            # 获取增强的材料
            evidence = rag_service.retrieve_evidence(
                query=query,
                top_k=3,
                include_kg=True
            )
            
            if evidence and evidence.get("evidence"):
                logger.info(f"RAG为子章节写作 '{subchapter_title}' 提供了 {len(evidence['evidence'])} 条参考材料")
                
                # 构建参考材料文本
                reference_materials = []
                for i, ev in enumerate(evidence["evidence"], 1):
                    content_preview = ev["content"][:300] + "..." if len(ev["content"]) > 300 else ev["content"]
                    reference_materials.append(f"[{i}] {content_preview}")
                
                return f"\n\n## 写作参考材料\n" + "\n\n".join(reference_materials) + "\n\n"
            else:
                logger.debug(f"RAG未找到子章节写作 '{subchapter_title}' 的相关材料")
                return ""
                
        except Exception as e:
            logger.warning(f"RAG写作增强失败: {e}")
            return ""

    def write_subchapter(
        self,
        subchapter_title: str,
        subchapter_outline: str,
        subchapter_keywords: List[str],
        research_summary: str,
        chapter_title: str,
        state: TextbookState,
    ) -> str:
        try:
            topic = state.get("topic")
            if not topic:
                raise RuntimeError("缺少必需字段: topic")
            language = state.get("language", "中文")
            rewrite_suggestions = state.get("rewrite_suggestions", "")
            rewrite_instructions = ""
            if rewrite_suggestions:
                rewrite_instructions = f"重写建议：{rewrite_suggestions}\n\n请根据以上重写建议进行改进。"
            
            # RAG增强：获取参考材料
            rag_materials = self._enhance_writing_with_rag(topic, subchapter_title, subchapter_keywords, research_summary)
            enhanced_research_summary = research_summary + rag_materials
            
            keywords_str = ", ".join(subchapter_keywords) if subchapter_keywords else "无"
            prompt = self.writer_prompt_template.format(
                topic=topic,
                subchapter_title=subchapter_title,
                subchapter_outline=subchapter_outline,
                subchapter_keywords=keywords_str,
                research_summary=enhanced_research_summary,  # 使用增强后的研究总结
                chapter_title=chapter_title,
                language=language,
                rewrite_instructions=rewrite_instructions,
            )
            # Use migration helper for YAML-based call
            from ...services.migration_service import migration_helper
            content = migration_helper.call_writer(
                topic=topic,
                subchapter_title=subchapter_title,
                subchapter_outline=subchapter_outline,
                subchapter_keywords=keywords_str,
                research_summary=enhanced_research_summary,  # 传递增强后的研究总结
                chapter_title=chapter_title,
                language=language,
                rewrite_instructions=rewrite_instructions
            )
            if not content or content.strip() == "":
                raise RuntimeError(f"子章节 '{subchapter_title}' 内容生成失败（API空响应）")
            return content
        except Exception as e:
            logger.error(f"为子章节 '{subchapter_title}' 生成内容时出错: {e}")
            raise

    def execute(self, state: TextbookState) -> TextbookState:
        subchapter_title = state.get("subchapter_title", "")
        subchapter_outline = state.get("subchapter_outline", "")
        subchapter_keywords = state.get("subchapter_keywords", [])
        subchapter_research_summary = state.get("subchapter_research_summary", "")
        chapter_title = state.get("chapter_title", "")
        topic = state.get("topic", "")

        if not subchapter_title:
            raise RuntimeError("缺少子章节标题，无法生成内容")
        if not subchapter_outline:
            raise RuntimeError(f"子章节 '{subchapter_title}' 缺少大纲信息，无法写作")
        if not topic:
            raise RuntimeError("缺少必需字段: topic")

        logger.info(f"Writer 开始执行，子章节: {subchapter_title}")
        logger.info(f"主题: {topic}")
        logger.info(f"关键词数量: {len(subchapter_keywords)}")

        content = self.write_subchapter(
            subchapter_title=subchapter_title,
            subchapter_outline=subchapter_outline,
            subchapter_keywords=subchapter_keywords,
            research_summary=subchapter_research_summary,
            chapter_title=chapter_title,
            state=state,
        )

        if "content" not in state:
            state["content"] = {}
        state["content"][subchapter_title] = content
        logger.info(f"Writer 完成，子章节: {subchapter_title}")
        logger.info(f"生成的内容长度: {len(str(content))}")
        if len(str(content)) < 500:
            logger.warning(f"子章节 '{subchapter_title}' 内容过短，可能生成失败")
        return state

__all__ = ["Writer"]

