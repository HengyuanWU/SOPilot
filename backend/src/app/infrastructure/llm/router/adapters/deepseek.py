#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek Adapter - DeepSeek API implementation (OpenAI-compatible).
"""

import logging
from typing import Optional
from .openai import OpenAIAdapter

logger = logging.getLogger(__name__)


class DeepSeekAdapter(OpenAIAdapter):
    """
    DeepSeek API adapter.
    
    DeepSeek uses OpenAI-compatible API format, so we inherit from
    OpenAIAdapter and only override the default configuration.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        self.description = "DeepSeek API Adapter (OpenAI-compatible)"
        self.default_base_url = "https://api.deepseek.com/v1"