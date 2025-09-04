#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SiliconFlow Adapter - SiliconFlow API implementation (OpenAI-compatible).
"""

import logging
from typing import Optional
from .openai import OpenAIAdapter

logger = logging.getLogger(__name__)


class SiliconFlowAdapter(OpenAIAdapter):
    """
    SiliconFlow API adapter.
    
    SiliconFlow uses OpenAI-compatible API format, so we inherit from
    OpenAIAdapter and only override the default configuration.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        self.description = "SiliconFlow API Adapter (OpenAI-compatible)"
        self.default_base_url = "https://api.siliconflow.cn/v1"