#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Router - Modern LLM client architecture with adapter pattern.
Replaces the old facade-based approach with a clean, extensible design.
"""

from .core import LLMRouter, llm_router
from .adapters import OpenAIAdapter, SiliconFlowAdapter, DeepSeekAdapter
from .types import LLMRequest, LLMResponse, LLMError

__all__ = [
    'LLMRouter',
    'llm_router',
    'OpenAIAdapter', 
    'SiliconFlowAdapter',
    'DeepSeekAdapter',
    'LLMRequest',
    'LLMResponse', 
    'LLMError'
]