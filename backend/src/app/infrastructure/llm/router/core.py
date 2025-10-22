#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Router Core - Central routing and orchestration for LLM calls.
"""

import time
import logging
from typing import Dict, Type, Optional
from .types import (
    LLMRequest, LLMResponse, ProviderType, 
    LLMException, LLMNetworkError, LLMRateLimitError, LLMServerError
)
from .adapters.base import BaseLLMAdapter
from .adapters.openai import OpenAIAdapter
from .adapters.siliconflow import SiliconFlowAdapter  
from .adapters.deepseek import DeepSeekAdapter

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Central LLM router with adapter pattern.
    
    Features:
    - Multi-provider support with unified interface
    - Automatic retry with exponential backoff
    - Request/response logging and metrics
    - Provider failover capabilities
    - Timeout and error handling
    """
    
    def __init__(self):
        self._adapters: Dict[str, BaseLLMAdapter] = {}
        self.logger = logging.getLogger(__name__)
        self._register_default_adapters()
        
    def _register_default_adapters(self):
        """Register built-in adapters."""
        self.register_adapter("openai", OpenAIAdapter())
        self.register_adapter("siliconflow", SiliconFlowAdapter())
        self.register_adapter("deepseek", DeepSeekAdapter())
        
    def register_adapter(self, provider: str, adapter: BaseLLMAdapter):
        """
        Register a new LLM adapter.
        
        Args:
            provider: Provider name (e.g., "openai", "siliconflow")
            adapter: Adapter instance
        """
        self._adapters[provider] = adapter
        logger.info(f"Registered LLM adapter: {provider}")
        
    def get_adapter(self, provider: str) -> BaseLLMAdapter:
        """
        Get adapter for the specified provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Adapter instance
            
        Raises:
            ValueError: If provider not supported
        """
        if provider not in self._adapters:
            available = list(self._adapters.keys())
            raise ValueError(f"Unsupported provider '{provider}'. Available: {available}")
            
        return self._adapters[provider]
        
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response using the specified provider.
        
        Args:
            request: LLM request object
            
        Returns:
            LLM response object
            
        Raises:
            LLMException: For various LLM-related errors
        """
        start_time = time.time()
        
        try:
            # Validate request
            self._validate_request(request)
            
            # Get adapter
            adapter = self.get_adapter(request.provider)
            
            # Log request
            self._log_request(request)
            
            # Execute request
            response = adapter.generate(request)
            
            # Add latency to response
            response.latency_ms = int((time.time() - start_time) * 1000)
            
            # Log response
            self._log_response(response)
            
            return response
            
        except LLMException:
            # Re-raise LLM exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            logger.error(f"Unexpected error in LLM router: {e}", exc_info=True)
            raise LLMException(
                f"Unexpected error: {str(e)}", 
                "internal", 
                request.provider,
                False,
                e
            )
    
    def generate_embedding_batch(self, request: LLMRequest) -> LLMResponse:
        """
        批量生成文本嵌入向量
        
        Args:
            request: LLM请求，包含待嵌入的文本列表（input_texts字段）
            
        Returns:
            包含embedding向量列表的响应
            
        Raises:
            LLMException: API调用失败时抛出
        """
        start_time = time.time()
        
        try:
            # 验证请求
            if not hasattr(request, 'input_texts') or not request.input_texts:
                raise ValueError("批量Embedding请求必须包含input_texts字段")
            
            # 获取适配器
            adapter = self.get_adapter(request.provider)
            
            # 检查适配器是否支持批量embedding
            if not hasattr(adapter, 'generate_embedding_batch'):
                raise LLMException(
                    f"Provider {request.provider} does not support batch embedding",
                    "unsupported_operation",
                    request.provider
                )
            
            # 调用适配器的批量embedding方法
            response = adapter.generate_embedding_batch(request)
            
            # 设置延迟
            latency_ms = int((time.time() - start_time) * 1000)
            if response:
                response.latency_ms = latency_ms
            
            logger.info(
                f"批量Embedding成功: provider={request.provider}, "
                f"model={request.model}, count={len(request.input_texts)}, latency={latency_ms}ms"
            )
            
            return response
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            # 使用module-level logger以避免异常处理中的潜在问题
            logger.error(
                f"批量Embedding失败: provider={request.provider}, "
                f"model={request.model}, error={str(e)}, latency={latency_ms}ms"
            )
            raise LLMException(
                f"批量Embedding失败: {str(e)}",
                "embedding_error",
                request.provider
            )
    
    def generate_embedding(self, request: LLMRequest) -> LLMResponse:
        """
        生成文本嵌入向量（IMPROOVE_GUIDE.md第5.4节要求）
        
        专门用于embedding API调用，支持实体链接中的向量相似度计算
        
        Args:
            request: LLM请求，包含待嵌入的文本
            
        Returns:
            包含embedding向量的响应
            
        Raises:
            LLMException: API调用失败时抛出
        """
        start_time = time.time()
        
        try:
            # 验证请求
            if not hasattr(request, 'input_text') or not request.input_text:
                raise ValueError("Embedding请求必须包含input_text字段")
            
            # 获取适配器
            adapter = self.get_adapter(request.provider)
            
            # 检查适配器是否支持embedding
            if not hasattr(adapter, 'generate_embedding'):
                raise LLMException(
                    f"Provider {request.provider} does not support embedding",
                    "unsupported_operation",
                    request.provider,
                    False
                )
            
            # 记录请求
            logger.debug(f"Embedding request: provider={request.provider}, model={request.model}, text_length={len(request.input_text)}")
            
            # 执行embedding
            response = adapter.generate_embedding(request)
            
            # 添加延迟信息
            response.latency_ms = int((time.time() - start_time) * 1000)
            
            # 记录响应
            logger.debug(f"Embedding response: provider={request.provider}, vector_dim={len(response.embedding) if hasattr(response, 'embedding') else 0}")
            
            return response
            
        except LLMException:
            # 重新抛出LLM异常
            raise
        except Exception as e:
            # 包装意外异常
            logger.error(f"Embedding API调用失败: {e}", exc_info=True)
            raise LLMException(
                f"Embedding调用失败: {str(e)}", 
                "embedding_error", 
                request.provider,
                False,
                e
            )

    def generate_with_retry(self, request: LLMRequest, max_retries: int = 3,
                           base_delay: float = 1.0, max_delay: float = 60.0) -> LLMResponse:
        """
        Generate response with automatic retry on transient errors.
        
        Args:
            request: LLM request object
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds
            
        Returns:
            LLM response object
            
        Raises:
            LLMException: If all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return self.generate(request)
                
            except (LLMNetworkError, LLMRateLimitError, LLMServerError) as e:
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"All retry attempts failed for {request.provider}:{request.model}")
                    raise
                
                # Calculate delay with exponential backoff
                delay = min(base_delay * (2 ** attempt), max_delay)
                
                # Add jitter
                import random
                delay *= (0.5 + random.random() * 0.5)
                
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                time.sleep(delay)
                
            except LLMException:
                # Non-retryable errors
                raise
        
        # This shouldn't be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise LLMException("Unknown retry failure", "internal", request.provider)
    
    def _validate_request(self, request: LLMRequest):
        """Validate LLM request parameters."""
        if not request.model:
            raise ValueError("Model is required")
        if not request.messages:
            raise ValueError("Messages list cannot be empty")
        if request.temperature < 0 or request.temperature > 2:
            raise ValueError("Temperature must be between 0 and 2")
        if request.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
            
    def _log_request(self, request: LLMRequest):
        """Log LLM request details."""
        logger.debug(
            f"LLM Request: {request.provider}:{request.model} "
            f"messages={len(request.messages)} temp={request.temperature} "
            f"max_tokens={request.max_tokens}"
        )
        
    def _log_response(self, response: LLMResponse):
        """Log LLM response details."""
        usage = response.usage
        logger.debug(
            f"LLM Response: {response.provider}:{response.model} "
            f"latency={response.latency_ms}ms "
            f"tokens={usage.get('total_tokens', 'unknown')}"
        )
    
    def get_supported_providers(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about supported providers.
        
        Returns:
            Dictionary mapping provider names to their info
        """
        providers = {}
        for provider_name, adapter in self._adapters.items():
            providers[provider_name] = {
                "name": provider_name,
                "class": adapter.__class__.__name__,
                "description": getattr(adapter, 'description', 'No description available')
            }
        return providers


# Global router instance
llm_router = LLMRouter()