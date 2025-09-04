#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Router Types - Type definitions for the router system.
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum


class ProviderType(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    SILICONFLOW = "siliconflow"
    DEEPSEEK = "deepseek"


@dataclass
class LLMMessage:
    """Represents a single message in a conversation."""
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMRequest:
    """Request object for LLM calls."""
    provider: str
    model: str
    messages: List[Dict[str, str]]  # Compatible with dict format
    temperature: float = 0.7
    max_tokens: int = 1500
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[Union[str, List[str]]] = None
    timeout: int = 300
    tags: Optional[Dict[str, str]] = None
    stream: bool = False


@dataclass
class LLMResponse:
    """Response object from LLM calls."""
    content: str
    model: str
    provider: str
    usage: Dict[str, int]
    latency_ms: int
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMError:
    """Error information from LLM calls."""
    error_type: str  # network, rate_limit, server, invalid_request, timeout
    message: str
    provider: str
    model: Optional[str] = None
    status_code: Optional[int] = None
    retryable: bool = False
    original_error: Optional[Exception] = None


class LLMException(Exception):
    """Base exception for LLM operations."""
    
    def __init__(self, message: str, error_type: str = "unknown", 
                 provider: str = "", retryable: bool = False, 
                 original_error: Optional[Exception] = None):
        super().__init__(message)
        self.error_type = error_type
        self.provider = provider
        self.retryable = retryable
        self.original_error = original_error


class LLMNetworkError(LLMException):
    """Network-related errors (timeouts, connection failures)."""
    
    def __init__(self, message: str, provider: str = "", original_error: Optional[Exception] = None):
        super().__init__(message, "network", provider, True, original_error)


class LLMRateLimitError(LLMException):
    """Rate limiting errors (429 responses)."""
    
    def __init__(self, message: str, provider: str = "", retry_after: Optional[int] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(message, "rate_limit", provider, True, original_error)
        self.retry_after = retry_after


class LLMServerError(LLMException):
    """Server-side errors (5xx responses)."""
    
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(message, "server", provider, True, original_error)
        self.status_code = status_code


class LLMInvalidRequestError(LLMException):
    """Client-side errors (4xx responses, invalid parameters)."""
    
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(message, "invalid_request", provider, False, original_error)
        self.status_code = status_code