#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Adapter - OpenAI API implementation.
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional, List
from .base import BaseLLMAdapter
from ..types import LLMRequest, LLMResponse, LLMException, LLMNetworkError

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI API adapter with standard OpenAI format support.
    
    Supports:
    - Official OpenAI API
    - OpenAI-compatible providers (with custom base_url)
    - Proper error handling and response formatting
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        self.description = "OpenAI API Adapter"
        self.default_base_url = "https://api.openai.com/v1"
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response using OpenAI API.
        
        Args:
            request: Standardized LLM request
            
        Returns:
            Standardized LLM response
            
        Raises:
            LLMException: For various API errors
        """
        # Get configuration
        api_key = self._get_api_key(request)
        base_url = self._get_base_url(request) or self.default_base_url
        
        # Prepare request payload
        payload = self._build_payload(request)
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SOPilot/1.0"
        }
        
        # Make API call
        url = f"{base_url.rstrip('/')}/chat/completions"
        
        try:
            # 设置更保守的超时配置
            timeout_config = httpx.Timeout(
                connect=30.0,  # 连接超时
                read=120.0,    # 读取超时 
                write=30.0,    # 写入超时
                pool=30.0      # 连接池超时
            )
            with httpx.Client(timeout=timeout_config) as client:
                response = client.post(url, json=payload, headers=headers)
                
                # Handle HTTP errors
                if response.status_code != 200:
                    error_text = response.text
                    raise self._handle_http_error(
                        response.status_code, error_text, request.provider
                    )
                
                # Parse response
                response_data = response.json()
                
                # Extract content and usage
                content = self._validate_response(response_data)
                usage = self._extract_usage_info(response_data)
                
                return LLMResponse(
                    content=content,
                    model=response_data.get('model', request.model),
                    provider=request.provider,
                    usage=usage,
                    latency_ms=0,  # Will be set by router
                    metadata={
                        "finish_reason": response_data.get('choices', [{}])[0].get('finish_reason'),
                        "api_version": response_data.get('api_version'),
                        "request_id": response.headers.get('x-request-id')
                    }
                )
                
        except httpx.TimeoutException as e:
            raise LLMNetworkError(
                f"Request timeout after {request.timeout}s",
                request.provider,
                e
            )
        except httpx.NetworkError as e:
            raise LLMNetworkError(
                f"Network error: {str(e)}",
                request.provider,
                e
            )
        except json.JSONDecodeError as e:
            raise LLMException(
                f"Invalid JSON response: {str(e)}",
                "format",
                request.provider,
                False,
                e
            )
        except httpx.RemoteProtocolError as e:
            # 专门处理服务器断开连接的问题
            logger.warning(
                f"Server disconnected for provider {request.provider}, "
                f"model {request.model}, payload size: {len(str(payload))} chars"
            )
            raise LLMNetworkError(
                f"Server disconnected without response (payload size: {len(str(payload))})",
                request.provider,
                e
            )
        except Exception as e:
            if isinstance(e, LLMException):
                raise
            logger.error(
                f"Unexpected error for provider {request.provider}: {str(e)}, "
                f"payload size: {len(str(payload))} chars"
            )
            raise LLMException(
                f"Unexpected error: {str(e)}",
                "internal",
                request.provider,
                False,
                e
            )
    
    def _build_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """
        Build OpenAI API request payload.
        
        Args:
            request: Standardized LLM request
            
        Returns:
            Dictionary ready for JSON serialization
        """
        payload = {
            "model": request.model,
            "messages": self._format_messages(request.messages),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty
        }
        
        # Add optional parameters
        if request.stop:
            payload["stop"] = request.stop
        
        if request.stream:
            payload["stream"] = True
            
        return payload
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Format messages for OpenAI API.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Formatted messages list
        """
        formatted = []
        
        for msg in messages:
            formatted_msg = {
                "role": msg["role"],
                "content": msg["content"]
            }
            
            # Add optional fields if present
            if "name" in msg:
                formatted_msg["name"] = msg["name"]
            if "tool_call_id" in msg:
                formatted_msg["tool_call_id"] = msg["tool_call_id"]
                
            formatted.append(formatted_msg)
        
        return formatted