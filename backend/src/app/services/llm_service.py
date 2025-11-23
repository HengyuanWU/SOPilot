#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Service - High-level interface integrating PromptService and LLMRouter.
Replaces the old llm_call function with a modern, YAML-based approach.
"""

import logging
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass

from .prompt_service import prompt_service
from ..infrastructure.llm.router import llm_router
from ..infrastructure.llm.router.types import LLMRequest, LLMResponse, LLMException

logger = logging.getLogger(__name__)


@dataclass
class LLMCallResult:
    """Result from LLM call with additional metadata."""
    content: str
    model: str
    provider: str
    usage: Dict[str, int]
    latency_ms: int
    prompt_id: str
    agent_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMService:
    """
    High-level LLM service providing agent-based prompt calls.
    
    Features:
    - YAML-based prompt management
    - Agent/workflow/locale binding resolution
    - Automatic retry and error handling
    - Usage tracking and logging
    - Template variable validation
    """
    
    def __init__(self):
        self.prompt_service = prompt_service
        self.llm_router = llm_router
    
    def call_agent(self, agent_name: str, variables: Dict[str, Any], 
                   locale: str = "zh", max_retries: int = 3,
                   timeout: int = 300, tags: Optional[Dict[str, str]] = None) -> LLMCallResult:
        """
        Call an agent with YAML-based prompt.
        
        Args:
            agent_name: Name of the agent (e.g., "planner", "writer")
            variables: Template variables for prompt rendering
            locale: Language locale
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
            tags: Additional tags for logging/tracing
            
        Returns:
            LLMCallResult with response and metadata
            
        Raises:
            LLMException: For various LLM-related errors
            ValueError: For invalid parameters
        """
        try:
            # Get rendered prompt
            rendered_prompt = self.prompt_service.get_prompt(
                target_type="agent",
                target_id=agent_name,
                variables=variables,
                locale=locale
            )
            
            # Build LLM request
            request = LLMRequest(
                provider=rendered_prompt.binding.provider,
                model=rendered_prompt.binding.model,
                messages=rendered_prompt.messages,
                temperature=rendered_prompt.meta.get('temperature', 0.7),
                max_tokens=rendered_prompt.meta.get('max_tokens', 1500),
                top_p=rendered_prompt.meta.get('top_p', 0.9),
                frequency_penalty=rendered_prompt.meta.get('frequency_penalty', 0.0),
                presence_penalty=rendered_prompt.meta.get('presence_penalty', 0.0),
                timeout=timeout,
                tags=tags or {}
            )
            
            # Add agent info to tags
            request.tags.update({
                "agent": agent_name,
                "locale": locale,
                "prompt_id": rendered_prompt.binding.prompt_file
            })
            
            # Execute with retry
            response = self.llm_router.generate_with_retry(
                request, max_retries=max_retries
            )
            
            # Log successful call
            logger.info(
                f"LLM call successful: {agent_name}@{locale} "
                f"({response.provider}:{response.model}) "
                f"tokens={response.usage.get('total_tokens', 'unknown')} "
                f"latency={response.latency_ms}ms"
            )
            
            return LLMCallResult(
                content=response.content,
                model=response.model,
                provider=response.provider,
                usage=response.usage,
                latency_ms=response.latency_ms,
                prompt_id=rendered_prompt.binding.prompt_file,
                agent_name=agent_name,
                metadata=response.metadata
            )
            
        except Exception as e:
            logger.error(
                f"LLM call failed: {agent_name}@{locale} - {str(e)}",
                exc_info=True
            )
            raise
    
    def call_workflow(self, workflow_name: str, variables: Dict[str, Any],
                     locale: str = "zh", **kwargs) -> LLMCallResult:
        """
        Call a workflow-level prompt.
        
        Args:
            workflow_name: Name of the workflow
            variables: Template variables
            locale: Language locale
            **kwargs: Additional parameters for call_agent
            
        Returns:
            LLMCallResult with response and metadata
        """
        try:
            # Get rendered prompt
            rendered_prompt = self.prompt_service.get_prompt(
                target_type="workflow",
                target_id=workflow_name,
                variables=variables,
                locale=locale
            )
            
            # Use same logic as call_agent but with workflow context
            request = LLMRequest(
                provider=rendered_prompt.binding.provider,
                model=rendered_prompt.binding.model,
                messages=rendered_prompt.messages,
                temperature=rendered_prompt.meta.get('temperature', 0.7),
                max_tokens=rendered_prompt.meta.get('max_tokens', 1500),
                timeout=kwargs.get('timeout', 300),
                tags=kwargs.get('tags', {})
            )
            
            request.tags.update({
                "workflow": workflow_name,
                "locale": locale,
                "prompt_id": rendered_prompt.binding.prompt_file
            })
            
            response = self.llm_router.generate_with_retry(
                request, max_retries=kwargs.get('max_retries', 3)
            )
            
            return LLMCallResult(
                content=response.content,
                model=response.model,
                provider=response.provider,
                usage=response.usage,
                latency_ms=response.latency_ms,
                prompt_id=rendered_prompt.binding.prompt_file,
                metadata=response.metadata
            )
            
        except Exception as e:
            logger.error(
                f"Workflow call failed: {workflow_name}@{locale} - {str(e)}",
                exc_info=True
            )
            raise
    
    def validate_template(self, agent_name: str, variables: Dict[str, Any],
                         locale: str = "zh") -> Dict[str, Any]:
        """
        Validate template rendering without making LLM call.
        
        Args:
            agent_name: Name of the agent
            variables: Template variables
            locale: Language locale
            
        Returns:
            Dictionary with validation results
        """
        try:
            rendered_prompt = self.prompt_service.get_prompt(
                target_type="agent",
                target_id=agent_name,
                variables=variables,
                locale=locale
            )
            
            return {
                "valid": True,
                "messages": rendered_prompt.messages,
                "meta": rendered_prompt.meta,
                "binding": {
                    "provider": rendered_prompt.binding.provider,
                    "model": rendered_prompt.binding.model,
                    "prompt_file": rendered_prompt.binding.prompt_file
                },
                "errors": []
            }
            
        except Exception as e:
            return {
                "valid": False,
                "messages": [],
                "meta": {},
                "binding": {},
                "errors": [str(e)]
            }
    
    def get_agent_info(self, agent_name: str, locale: str = "zh") -> Dict[str, Any]:
        """
        Get information about an agent and its prompt configuration.
        
        Args:
            agent_name: Name of the agent
            locale: Language locale
            
        Returns:
            Dictionary with agent information
        """
        try:
            binding = self.prompt_service.resolve_binding(
                target_type="agent",
                target_id=agent_name,
                locale=locale
            )
            
            return {
                "agent": agent_name,
                "locale": locale,
                "provider": binding.provider,
                "model": binding.model,
                "prompt_file": binding.prompt_file,
                "params": binding.params,
                "available": True
            }
            
        except Exception as e:
            return {
                "agent": agent_name,
                "locale": locale,
                "available": False,
                "error": str(e)
            }
    
    def call_structured(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用LLM进行结构化输出（按IMPROOVE_GUIDE.md第5.2.1节要求）
        
        专门用于KG关系抽取等需要JSON Schema约束的场景
        
        Args:
            payload: 包含task, text, candidates, language, schema等字段
            
        Returns:
            结构化的LLM响应，符合提供的JSON Schema
        """
        try:
            task = payload.get("task", "relation_extraction")
            text = payload.get("text", "")
            candidates = payload.get("candidates", [])
            language = payload.get("language", "zh")
            schema = payload.get("schema", {})
            
            if not text:
                return {"relations": []}
            
            # 构建结构化提示（按指南要求）
            system_prompt = """你是一个知识图谱关系抽取专家。请从给定的句子中抽取实体间的关系。

要求：
1. 只抽取句子中明确存在的关系
2. 实体必须在句子中出现或与候选实体匹配
3. 关系类型限定为：RELATES_TO, PART_OF, REQUIRES, IMPLEMENTS, CONTRASTS_WITH, DEFINES, EXPLAINS, SIMILAR_TO
4. 为每个关系提供0.0-1.0的置信度分数
5. 严格按照JSON格式返回"""

            user_prompt = f"""句子：{text}

候选实体：{', '.join(candidates) if candidates else '无'}

请按以下JSON格式返回关系：
{{"relations": [{{"head": "实体1", "relation": "关系类型", "tail": "实体2", "confidence": 0.85}}]}}

如果没有发现关系，返回：{{"relations": []}}"""

            # 构建LLM请求（指南要求：温度0.1，SiliconFlow提供商）
            request = LLMRequest(
                provider="siliconflow",  # 指南要求默认提供商
                model="Qwen/Qwen2.5-7B-Instruct",  # 指南要求的模型
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # 指南要求固定温度
                max_tokens=500,
                timeout=30,
                tags={"task": task, "structured": "true"}
            )
            
            # 调用LLM
            response = self.llm_router.generate(request)
            
            # 使用 LangChain parser 解析响应（替代手动JSON解析）
            from ..infrastructure.llm.parsers import parse_kg_relations
            return parse_kg_relations(response.content)
                
        except Exception as e:
            logger.error(f"Structured LLM call failed: {e}")
            return {"relations": []}


# Legacy compatibility function
def llm_call(prompt: str, api_type: str = "siliconflow", 
             max_tokens: int = 1500, agent_name: str = "unknown",
             temperature: float = 0.7, **kwargs) -> str:
    """
    Legacy compatibility function for old llm_call interface.
    
    DEPRECATED: Use LLMService.call_agent() with YAML prompts instead.
    
    This function provides backward compatibility during migration but
    should be replaced with proper agent-based calls.
    """
    logger.warning(
        f"DEPRECATED: llm_call() is deprecated. "
        f"Use LLMService.call_agent() for agent '{agent_name}' instead."
    )
    
    try:
        # Create a simple request using the legacy prompt
        request = LLMRequest(
            provider=api_type,
            model=kwargs.get('model', 'Qwen/Qwen3-Coder-30B-A3B-Instruct'),
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=kwargs.get('timeout', 300),
            tags={"legacy": "true", "agent": agent_name}
        )
        
        response = llm_router.generate(request)
        return response.content
        
    except Exception as e:
        logger.error(f"Legacy llm_call failed: {e}")
        raise


# Global service instance
llm_service = LLMService()