import logging
import hashlib
import re
from typing import Dict, List, Any
from datetime import datetime
from app.domain.state.textbook_state import TextbookState
from app.infrastructure.llm.client import llm_call

logger = logging.getLogger(__name__)


class KGBuilder:
    def __init__(self, provider: str = "siliconflow"):
        self.provider = provider
        self.kg_prompt_template = (
            "你是一位专业的知识图谱专家，正在为《{topic}》教材构建知识图谱。\n\n"
            "教材内容：\n{content_text}\n\n"
            "关键词：{keywords}\n\n"
            "请务必根据教材内容以及关键词，提取出一个2-3层的知识图谱，包含：\n"
            "1. 核心概念节点\n"
            "2. 概念间的关系\n"
            "3. 层次结构\n\n"
            "输出格式：\n"
            "## 知识图谱\n"
            "### 节点\n"
            "- 节点1: [概念描述]\n"
            "- 节点2: [概念描述]\n"
            "...\n\n"
            "### 关系\n"
            "- 节点1 -> 节点2: [关系类型]\n"
            "- 节点2 -> 节点3: [关系类型]\n"
            "...\n\n"
            "### 层次结构\n"
            "- 第一层: [核心概念]\n"
            "  - 第二层: [子概念]\n"
            "    - 第三层: [具体概念]\n"
            "...\n\n"
            "请确保知识图谱结构清晰，关系准确，适合{language}教学。"
        )

    def build_knowledge_graph(
        self,
        topic: str,
        content: Dict[str, str],
        keywords: List[str],
        language: str = "中文",
        chapter_title: str = None,
        subchapter_title: str = None,
    ) -> Dict[str, Any]:
        try:
            content_text = ""
            for subchapter, subchapter_content in content.items():
                content_text += f"\n## {subchapter}\n{subchapter_content}\n"
            keywords_str = ", ".join(keywords) if keywords else "无"
            prompt = self.kg_prompt_template.format(
                topic=topic, content_text=content_text[:3000], keywords=keywords_str, language=language
            )
            kg_content = llm_call(prompt, api_type=self.provider, max_tokens=2000, agent_name="KGBuilder")
            if not kg_content or kg_content.strip() == "":
                raise RuntimeError(f"主题 '{topic}' 知识图谱生成失败（API空响应）")
            return self._parse_knowledge_graph(kg_content, topic, chapter_title, subchapter_title)
        except Exception as e:
            logger.error(f"构建知识图谱时出错: {e}")
            raise

    def _slug(self, text: str) -> str:
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text)
        return cleaned.strip("_").lower()

    def _generate_section_id(self, topic: str, chapter: str, subchapter: str) -> str:
        content = f"{topic}|{chapter or ''}|{subchapter or ''}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    def _generate_concept_id(self, name: str, topic: str, chapter: str, subchapter: str) -> str:
        slug_name = self._slug(name)
        content = f"{topic}|{chapter or ''}|{subchapter or ''}"
        hash_suffix = hashlib.md5(content.encode("utf-8")).hexdigest()[:6]
        return f"concept:{slug_name}:{hash_suffix}"

    def _parse_knowledge_graph(self, content: str, topic: str, chapter_title: str = None, subchapter_title: str = None) -> Dict[str, Any]:
        try:
            current_time = datetime.utcnow().isoformat()
            nodes = []
            if "### 节点" in content:
                nodes_section = content.split("### 节点")[1].split("###")[0]
                for line in nodes_section.split("\n"):
                    if line.strip().startswith("- "):
                        node_text = line.strip()[2:]
                        if ":" in node_text:
                            node_name, node_desc = node_text.split(":", 1)
                            node_name = node_name.strip()
                            node_desc = node_desc.strip()
                            nodes.append({
                                "id": self._generate_concept_id(node_name, topic, chapter_title, subchapter_title),
                                "type": "concept",
                                "name": node_name,
                                "description": node_desc,
                                "canonical_key": self._slug(node_name),
                                "aliases": [],
                                "chapter": chapter_title or "未知章节",
                                "subchapter": subchapter_title or chapter_title or "未知子章节",
                                "score": 1.0,
                                "source": "llm_generated",
                                "created_at": current_time,
                                "updated_at": current_time,
                            })
            edges = []
            if "### 关系" in content:
                edges_section = content.split("### 关系")[1].split("###")[0]
                for line in edges_section.split("\n"):
                    if line.strip().startswith("- ") and "->" in line and ":" in line:
                        edge_parts, edge_type = line.strip()[2:].split(":", 1)
                        source_name, target_name = edge_parts.split("->", 1)
                        source_name = source_name.strip()
                        target_name = target_name.strip()
                        edge_type = edge_type.strip()
                        source_id = self._generate_concept_id(source_name, topic, chapter_title, subchapter_title)
                        target_id = self._generate_concept_id(target_name, topic, chapter_title, subchapter_title)
                        edge_id = f"{edge_type.upper()}:{source_id}->{target_id}"
                        edges.append({
                            "id": edge_id,
                            "type": edge_type.upper(),
                            "source_id": source_id,
                            "target_id": target_id,
                            "source_name": source_name,
                            "target_name": target_name,
                            "weight": 1.0,
                            "confidence": 0.8,
                            "evidence": f"从文本中抽取的关系: {source_name} -> {target_name}",
                            "chapter": chapter_title or "未知章节",
                            "src": self._generate_section_id(topic, chapter_title, subchapter_title),
                            "created_at": current_time,
                            "updated_at": current_time,
                        })
            hierarchy = ""
            if "### 层次结构" in content:
                hierarchy_section = content.split("### 层次结构")[1]
                hierarchy = hierarchy_section.strip()
            return {"nodes": nodes, "edges": edges, "hierarchy": hierarchy, "raw_content": content}
        except Exception as e:
            logger.error(f"解析知识图谱时出错: {e}")
            return {"nodes": [], "edges": [], "hierarchy": "", "raw_content": content}

    def execute(self, state: TextbookState) -> TextbookState:
        topic = state.get("topic")
        if not topic:
            raise RuntimeError("缺少必需字段: topic")
        content = state.get("content", {})
        keywords = state.get("keywords", [])
        language = state.get("language", "中文")
        chapter_title = state.get("chapter_title")
        subchapter_title = None
        if len(content) == 1:
            subchapter_title = list(content.keys())[0]
        logger.info(f"KGBuilder 开始执行，主题: {topic}")
        kg_result = self.build_knowledge_graph(topic, content, keywords, language, chapter_title, subchapter_title)
        state["kg"] = {"nodes": kg_result["nodes"], "edges": kg_result["edges"], "hierarchy": kg_result["hierarchy"]}
        state["kg_content"] = kg_result["raw_content"]
        state["kg_complete"] = True
        logger.info(f"KGBuilder 完成，节点数: {len(kg_result['nodes'])}, 边数: {len(kg_result['edges'])}")
        return state

__all__ = ["KGBuilder"]

