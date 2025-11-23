#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Output Parsers - Unified JSON/Pydantic parsing using LangChain.

Provides structured output parsing for:
- Textbook outline generation (planner.py)
- Knowledge graph relation extraction (llm_service.py, kg/builder.py)
- Generic JSON parsing with validation
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.exceptions import OutputParserException

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for Structured Outputs
# ============================================================================

class SubchapterOutline(BaseModel):
    """Subchapter outline structure."""
    title: str = Field(description="子章节标题")
    outline: str = Field(description="子章节概述，至少30字")


class ChapterOutline(BaseModel):
    """Chapter outline structure."""
    title: str = Field(description="章节标题")
    outline: str = Field(description="章节概述")
    subchapters: List[SubchapterOutline] = Field(description="子章节列表，2-4个")


class TextbookOutline(BaseModel):
    """Complete textbook outline structure."""
    chapters: List[ChapterOutline] = Field(description="章节列表")


class KGRelation(BaseModel):
    """Knowledge graph relation structure.
    
    Field names match LLM output format: head, relation, tail, confidence
    """
    head: str = Field(description="源实体")
    relation: str = Field(description="关系类型")
    tail: str = Field(description="目标实体")
    confidence: float = Field(description="置信度 (0.0-1.0)", ge=0.0, le=1.0)


class KGExtractionResult(BaseModel):
    """Knowledge graph extraction result."""
    relations: List[KGRelation] = Field(default_factory=list, description="提取的关系列表")


# ============================================================================
# Parser Factory
# ============================================================================

class OutputParserFactory:
    """Factory for creating LangChain output parsers."""
    
    @staticmethod
    def get_textbook_outline_parser() -> PydanticOutputParser:
        """
        Get parser for textbook outline.
        
        Returns:
            PydanticOutputParser configured for TextbookOutline
        """
        return PydanticOutputParser(pydantic_object=TextbookOutline)
    
    @staticmethod
    def get_kg_relation_parser() -> PydanticOutputParser:
        """
        Get parser for KG relation extraction.
        
        Returns:
            PydanticOutputParser configured for KGExtractionResult
        """
        return PydanticOutputParser(pydantic_object=KGExtractionResult)
    
    @staticmethod
    def get_json_parser() -> JsonOutputParser:
        """
        Get generic JSON parser (no schema validation).
        
        Returns:
            JsonOutputParser for flexible JSON parsing
        """
        return JsonOutputParser()


# ============================================================================
# Parsing Utilities
# ============================================================================

def parse_textbook_outline(llm_output: str) -> List[Dict[str, Any]]:
    """
    Parse textbook outline from LLM output.
    
    Replaces parse_outline_to_chapters() from planner.py.
    
    Args:
        llm_output: Raw LLM output (may contain markdown blocks)
        
    Returns:
        List of chapter dictionaries compatible with existing code
        
    Raises:
        OutputParserException: If parsing fails
        ValueError: If validation fails
    """
    parser = OutputParserFactory.get_textbook_outline_parser()
    
    try:
        # LangChain automatically handles ```json blocks and extracts JSON
        result = parser.parse(llm_output)
        
        # Convert Pydantic to dict format expected by existing code
        chapters = []
        for chapter in result.chapters:
            chapters.append({
                "title": chapter.title,
                "outline": chapter.outline,
                "subchapters": [
                    {
                        "title": sub.title,
                        "outline": sub.outline
                    }
                    for sub in chapter.subchapters
                ]
            })
        
        # Validation
        if not chapters:
            raise ValueError("规划结果缺少 chapters 或为空")
        
        for ch in chapters:
            if not ch["title"].strip():
                raise ValueError("存在章节缺少标题")
            if not ch["outline"].strip():
                raise ValueError(f"章节 '{ch['title']}' 缺少 outline")
            if not ch["subchapters"]:
                raise ValueError(f"章节 '{ch['title']}' 未包含任何子章节")
            
            for sub in ch["subchapters"]:
                if not sub["title"].strip():
                    raise ValueError("存在子章节缺少标题")
                if len(sub["outline"]) < 10:
                    raise ValueError(f"子章节 '{sub['title']}' 描述过短（需≥30字）")
        
        logger.info(f"成功解析教材大纲: {len(chapters)} 章")
        return chapters
        
    except OutputParserException as e:
        logger.error(f"LLM输出解析失败: {e}")
        raise RuntimeError(f"规划结果非 JSON 可解析格式: {e}")
    except Exception as e:
        logger.error(f"大纲验证失败: {e}")
        raise


def parse_kg_relations(llm_output: str) -> Dict[str, Any]:
    """
    Parse KG relations from LLM output.
    
    Replaces manual JSON parsing in llm_service.call_structured().
    
    Args:
        llm_output: Raw LLM output
        
    Returns:
        Dict with 'relations' key containing list of relation dicts
        Format: [{"head": "...", "relation": "...", "tail": "...", "confidence": 0.85}]
    """
    parser = OutputParserFactory.get_kg_relation_parser()
    
    try:
        result = parser.parse(llm_output)
        
        # Field names already match LLM output format (head, relation, tail, confidence)
        # Direct conversion to dict format expected by builder.py
        relations = [
            {
                "head": rel.head,
                "relation": rel.relation,
                "tail": rel.tail,
                "confidence": rel.confidence
            }
            for rel in result.relations
        ]
        
        logger.info(f"成功解析 {len(relations)} 条KG关系")
        return {"relations": relations}
        
    except OutputParserException as e:
        logger.warning(f"KG关系解析失败（OutputParserException），返回空结果: {e}")
        logger.debug(f"LLM输出内容（前500字符）: {llm_output[:500]}")
        return {"relations": []}
    except Exception as e:
        logger.error(f"KG关系提取异常: {e}", exc_info=True)
        logger.debug(f"LLM输出内容（前500字符）: {llm_output[:500]}")
        return {"relations": []}


def parse_json_flexible(llm_output: str, default: Any = None) -> Any:
    """
    Parse JSON from LLM output with flexible error handling.
    
    Args:
        llm_output: Raw LLM output
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON object or default value
    """
    parser = OutputParserFactory.get_json_parser()
    
    try:
        return parser.parse(llm_output)
    except OutputParserException as e:
        logger.warning(f"JSON解析失败，返回默认值: {e}")
        return default if default is not None else {}


def get_format_instructions(parser_type: str = "textbook_outline") -> str:
    """
    Get format instructions to append to prompts.
    
    Args:
        parser_type: Type of parser ("textbook_outline", "kg_relation", "json")
        
    Returns:
        Format instructions string
    """
    parsers = {
        "textbook_outline": OutputParserFactory.get_textbook_outline_parser(),
        "kg_relation": OutputParserFactory.get_kg_relation_parser(),
        "json": OutputParserFactory.get_json_parser()
    }
    
    parser = parsers.get(parser_type)
    if parser is None:
        raise ValueError(f"Unknown parser type: {parser_type}")
    
    return parser.get_format_instructions()


__all__ = [
    "TextbookOutline",
    "ChapterOutline",
    "SubchapterOutline",
    "KGRelation",
    "KGExtractionResult",
    "OutputParserFactory",
    "parse_textbook_outline",
    "parse_kg_relations",
    "parse_json_flexible",
    "get_format_instructions"
]


