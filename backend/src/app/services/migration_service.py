#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Service - Tools for migrating from old llm_call to new YAML-based system.
"""

import logging
from typing import Dict, Any, Optional

from .llm_service import llm_service, LLMCallResult

logger = logging.getLogger(__name__)


class AgentMigrationHelper:
    """
    Helper class to migrate agents from hardcoded prompts to YAML-based system.
    
    Provides backward-compatible interfaces while gradually migrating to
    the new PromptService + LLMRouter architecture.
    """
    
    def __init__(self):
        self.llm_service = llm_service
    
    def call_planner(self, topic: str, chapter_count: int = 5, language: str = "中文") -> str:
        """
        Migrated planner call using YAML prompt.
        
        Args:
            topic: 教材主题
            chapter_count: 章节数量
            language: 生成语言
            
        Returns:
            Generated outline as JSON string
        """
        try:
            variables = {
                "topic": topic,
                "chapter_count": chapter_count,
                "language": language
            }
            
            result = self.llm_service.call_agent(
                agent_name="planner",
                variables=variables,
                locale="zh"
            )
            
            logger.info(f"Planner call successful: {result.latency_ms}ms, {result.usage.get('total_tokens', 0)} tokens")
            return result.content
            
        except Exception as e:
            logger.error(f"Planner call failed: {e}")
            raise RuntimeError(f"主题 '{topic}' 大纲生成失败：{str(e)}")
    
    def call_researcher(self, topic: str, subchapter_title: str, 
                       subchapter_outline: str = "") -> Dict[str, Any]:
        """
        Migrated researcher call using YAML prompt.
        
        Args:
            topic: 教材主题
            subchapter_title: 子章节标题
            subchapter_outline: 子章节大纲
            
        Returns:
            Parsed research result dictionary
        """
        try:
            variables = {
                "topic": topic,
                "subchapter_title": subchapter_title,
                "subchapter_outline": subchapter_outline or "(无补充大纲)"
            }
            
            result = self.llm_service.call_agent(
                agent_name="researcher",
                variables=variables,
                locale="zh"
            )
            
            # Parse the research content using the same logic as before
            parsed_result = self._parse_research_content(result.content)
            
            logger.info(f"Researcher call successful: {result.latency_ms}ms, {result.usage.get('total_tokens', 0)} tokens")
            return parsed_result
            
        except Exception as e:
            logger.error(f"Researcher call failed: {e}")
            raise RuntimeError(f"子章节 '{subchapter_title}' 研究内容生成失败：{str(e)}")
    
    def call_writer(self, topic: str, subchapter_title: str, subchapter_outline: str,
                   subchapter_keywords: str, research_summary: str, chapter_title: str,
                   language: str = "中文", rewrite_instructions: str = "") -> str:
        """
        Migrated writer call using YAML prompt.
        
        Args:
            topic: 教材主题
            subchapter_title: 子章节标题
            subchapter_outline: 子章节大纲
            subchapter_keywords: 子章节关键词
            research_summary: 研究总结
            chapter_title: 章节标题
            language: 生成语言
            rewrite_instructions: 重写指令
            
        Returns:
            Generated content string
        """
        try:
            variables = {
                "topic": topic,
                "subchapter_title": subchapter_title,
                "subchapter_outline": subchapter_outline,
                "subchapter_keywords": subchapter_keywords,
                "research_summary": research_summary,
                "chapter_title": chapter_title,
                "language": language,
                "rewrite_instructions": rewrite_instructions
            }
            
            result = self.llm_service.call_agent(
                agent_name="writer",
                variables=variables,
                locale="zh"
            )
            
            logger.info(f"Writer call successful: {result.latency_ms}ms, {result.usage.get('total_tokens', 0)} tokens")
            return result.content
            
        except Exception as e:
            logger.error(f"Writer call failed: {e}")
            raise RuntimeError(f"子章节 '{subchapter_title}' 内容生成失败：{str(e)}")
    
    def call_validator(self, topic: str, subchapter_title: str, subchapter_content: str,
                      subchapter_outline: str, subchapter_keywords: str, 
                      research_summary: str) -> Dict[str, Any]:
        """
        Migrated validator call using YAML prompt.
        
        Args:
            topic: 教材主题
            subchapter_title: 子章节标题
            subchapter_content: 子章节内容
            subchapter_outline: 子章节大纲
            subchapter_keywords: 子章节关键词
            research_summary: 研究总结
            
        Returns:
            Parsed validation result dictionary
        """
        try:
            variables = {
                "topic": topic,
                "subchapter_title": subchapter_title,
                "subchapter_content": subchapter_content,
                "subchapter_outline": subchapter_outline,
                "subchapter_keywords": subchapter_keywords,
                "research_summary": research_summary
            }
            
            result = self.llm_service.call_agent(
                agent_name="validator",
                variables=variables,
                locale="zh"
            )
            
            # Parse the validation content
            parsed_result = self._parse_validation_content(result.content)
            
            logger.info(f"Validator call successful: {result.latency_ms}ms, {result.usage.get('total_tokens', 0)} tokens")
            return parsed_result
            
        except Exception as e:
            logger.error(f"Validator call failed: {e}")
            raise RuntimeError(f"子章节 '{subchapter_title}' 验证失败：{str(e)}")
    
    def call_qa_generator(self, topic: str, subchapter_title: str, subchapter_content: str,
                         subchapter_keywords: str, research_summary: str, 
                         language: str = "中文") -> Dict[str, Any]:
        """
        Migrated QA generator call using YAML prompt.
        
        Args:
            topic: 教材主题
            subchapter_title: 子章节标题
            subchapter_content: 子章节内容
            subchapter_keywords: 子章节关键词
            research_summary: 研究总结
            language: 生成语言
            
        Returns:
            Generated QA content dictionary
        """
        try:
            variables = {
                "topic": topic,
                "subchapter_title": subchapter_title,
                "subchapter_content": subchapter_content,
                "subchapter_keywords": subchapter_keywords,
                "research_summary": research_summary,
                "language": language
            }
            
            result = self.llm_service.call_agent(
                agent_name="qa_generator",
                variables=variables,
                locale="zh"
            )
            
            logger.info(f"QA Generator call successful: {result.latency_ms}ms, {result.usage.get('total_tokens', 0)} tokens")
            
            return {
                "qa_content": result.content,
                "qa_metadata": {
                    "model": result.model,
                    "provider": result.provider,
                    "usage": result.usage,
                    "latency_ms": result.latency_ms
                }
            }
            
        except Exception as e:
            logger.error(f"QA Generator call failed: {e}")
            raise RuntimeError(f"子章节 '{subchapter_title}' QA生成失败：{str(e)}")
    
    def call_kg_builder(self, topic: str, content_text: str, keywords: str, 
                       language: str = "中文") -> str:
        """
        Migrated KG builder call using YAML prompt.
        
        Args:
            topic: 教材主题
            content_text: 教材内容
            keywords: 关键词
            language: 生成语言
            
        Returns:
            Generated knowledge graph content
        """
        try:
            variables = {
                "topic": topic,
                "content_text": content_text,
                "keywords": keywords,
                "language": language
            }
            
            result = self.llm_service.call_agent(
                agent_name="kg_builder",
                variables=variables,
                locale="zh"
            )
            
            logger.info(f"KG Builder call successful: {result.latency_ms}ms, {result.usage.get('total_tokens', 0)} tokens")
            return result.content
            
        except Exception as e:
            logger.error(f"KG Builder call failed: {e}")
            raise RuntimeError(f"知识图谱构建失败：{str(e)}")
    
    def _parse_research_content(self, content: str) -> Dict[str, Any]:
        """Parse researcher output using the same logic as the original implementation."""
        subchapter_keywords = []
        subchapter_research_summary = ""
        subchapter_key_concepts = []
        
        if "## 子章节关键词" in content:
            section = content.split("## 子章节关键词")[1].split("##")[0]
            line = section.strip().split("\n")[0]
            subchapter_keywords = [kw.strip() for kw in line.split(",") if kw.strip()]
        
        if "## 子章节研究总结" in content:
            section = content.split("## 子章节研究总结")[1]
            if "##" in section:
                section = section.split("##")[0]
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
    
    def _parse_validation_content(self, content: str) -> Dict[str, Any]:
        """Parse validator output to extract score and pass/fail status."""
        import re
        
        # Extract overall score
        score_pattern = r"### 总体评分：(\d+(?:\.\d+)?)/10"
        score_match = re.search(score_pattern, content)
        score = float(score_match.group(1)) if score_match else 0.0
        
        # Extract pass/fail status
        pass_pattern = r"### 是否通过：(是|否)"
        pass_match = re.search(pass_pattern, content)
        is_passed = pass_match.group(1) == "是" if pass_match else False
        
        # Extract feedback (improvement suggestions)
        feedback = ""
        if "### 改进建议：" in content:
            feedback_section = content.split("### 改进建议：")[1]
            if "###" in feedback_section:
                feedback_section = feedback_section.split("###")[0]
            feedback = feedback_section.strip()
        
        return {
            "score": score,
            "is_passed": is_passed,
            "feedback": feedback,
            "raw_validation_content": content
        }


# Global migration helper instance
migration_helper = AgentMigrationHelper()