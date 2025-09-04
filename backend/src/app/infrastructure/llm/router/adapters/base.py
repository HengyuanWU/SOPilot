#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base LLM Adapter - Abstract base class for all provider adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import logging
import threading
from ..types import LLMRequest, LLMResponse, LLMException
from .....core.settings import get_settings

logger = logging.getLogger(__name__)


class BaseLLMAdapter(ABC):
    """
    Abstract base class for LLM provider adapters.
    
    Each provider adapter must implement the generate method and handle
    provider-specific authentication, error handling, and response formatting.
    """
    
    # Class-level round-robin counters for API key rotation
    _api_key_counters = {}
    _counter_lock = threading.Lock()
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize adapter with optional configuration.
        
        Args:
            api_key: API key for the provider
            base_url: Base URL for API endpoints
        """
        self.api_key = api_key
        self.base_url = base_url
        self.description = "Base LLM Adapter"
    
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response from the LLM provider.
        
        Args:
            request: Standardized LLM request
            
        Returns:
            Standardized LLM response
            
        Raises:
            LLMException: For provider-specific errors
        """
        pass
    
    def _get_api_key(self, request: LLMRequest) -> str:
        """
        Get API key from request tags, instance config, settings, or environment.
        Supports multiple API keys with round-robin load balancing.
        
        Args:
            request: LLM request (may contain API key in tags)
            
        Returns:
            API key string
            
        Raises:
            LLMException: If no API key found
        """
        # Priority: request tags > instance config > settings > environment
        api_key = None
        
        if request.tags and 'api_key' in request.tags:
            api_key = request.tags['api_key']
        elif self.api_key:
            api_key = self.api_key
        else:
            # Try to get API keys from settings first
            try:
                settings = get_settings()
                provider_config = settings.providers.get(request.provider)
                if provider_config and provider_config.api_keys:
                    # Multiple API keys - use round-robin
                    api_keys = provider_config.api_keys
                    with self._counter_lock:
                        if request.provider not in self._api_key_counters:
                            self._api_key_counters[request.provider] = 0
                        index = self._api_key_counters[request.provider] % len(api_keys)
                        self._api_key_counters[request.provider] += 1
                        api_key = api_keys[index]
                        logger.debug(f"Selected API key {index + 1}/{len(api_keys)} for provider {request.provider}")
            except Exception as e:
                logger.warning(f"Failed to load API keys from settings: {e}")
            
            # Fallback to environment variables if settings didn't work
            if not api_key:
                env_vars = [
                    f"APP_PROVIDERS__{request.provider.upper()}__API_KEY",
                    f"{request.provider.upper()}_API_KEY",
                    "OPENAI_API_KEY"  # Fallback for OpenAI-compatible providers
                ]
                
                for env_var in env_vars:
                    api_key = os.getenv(env_var)
                    if api_key:
                        break
        
        if not api_key:
            raise LLMException(
                f"No API key found for provider {request.provider}",
                "authentication",
                request.provider
            )
        
        return api_key
    
    def _get_base_url(self, request: LLMRequest) -> Optional[str]:
        """
        Get base URL from instance config or environment.
        
        Args:
            request: LLM request
            
        Returns:
            Base URL string or None
        """
        if self.base_url:
            return self.base_url
            
        # Try environment variable
        env_var = f"APP_PROVIDERS__{request.provider.upper()}__BASE_URL"
        return os.getenv(env_var)
    
    def _handle_http_error(self, status_code: int, response_text: str, 
                          provider: str) -> LLMException:
        """
        Convert HTTP error to appropriate LLMException.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            provider: Provider name
            
        Returns:
            Appropriate LLMException subclass
        """
        from ..types import (
            LLMNetworkError, LLMRateLimitError, 
            LLMServerError, LLMInvalidRequestError
        )
        
        if status_code == 429:
            return LLMRateLimitError(
                f"Rate limit exceeded: {response_text}",
                provider
            )
        elif 400 <= status_code < 500:
            return LLMInvalidRequestError(
                f"Client error ({status_code}): {response_text}",
                provider,
                status_code
            )
        elif 500 <= status_code < 600:
            return LLMServerError(
                f"Server error ({status_code}): {response_text}",
                provider,
                status_code
            )
        else:
            return LLMException(
                f"HTTP error ({status_code}): {response_text}",
                "http",
                provider
            )
    
    def _extract_usage_info(self, response_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Extract token usage information from provider response.
        
        Args:
            response_data: Raw response from provider
            
        Returns:
            Dictionary with usage statistics
        """
        usage = response_data.get('usage', {})
        return {
            'prompt_tokens': usage.get('prompt_tokens', 0),
            'completion_tokens': usage.get('completion_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0)
        }
    
    def _validate_response(self, response_data: Dict[str, Any]) -> str:
        """
        Validate and extract content from provider response.
        
        Args:
            response_data: Raw response from provider
            
        Returns:
            Extracted content string
            
        Raises:
            LLMException: If response format is invalid
        """
        try:
            choices = response_data.get('choices', [])
            if not choices:
                raise LLMException("No choices in response", "format", "unknown")
            
            choice = choices[0]
            message = choice.get('message', {})
            content = message.get('content', '')
            
            if not content:
                raise LLMException("Empty content in response", "format", "unknown")
            
            return content.strip()
            
        except (KeyError, IndexError, AttributeError) as e:
            raise LLMException(
                f"Invalid response format: {e}",
                "format",
                "unknown",
                False,
                e
            )