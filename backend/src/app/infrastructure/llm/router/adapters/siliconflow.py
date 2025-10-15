#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SiliconFlow Adapter - SiliconFlow API implementation (OpenAI-compatible).
"""

import logging
from typing import Optional, TYPE_CHECKING
from .openai import OpenAIAdapter

if TYPE_CHECKING:
    from ..types import LLMResponse, LLMRequest

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
    
    def generate_embedding_batch(self, request) -> 'LLMResponse':
        """
        批量生成文本嵌入向量
        
        使用SiliconFlow的embedding API（支持批量输入）
        """
        import httpx
        from ..types import LLMResponse
        
        try:
            # 获取API配置
            api_key = self._get_api_key(request)
            base_url = self._get_base_url(request) or self.default_base_url
            
            # 构建批量embedding请求（input可以是数组）
            payload = {
                "model": request.model,
                "input": request.input_texts  # 批量输入
            }
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "SOPilot/1.0"
            }
            
            # 调用embedding API
            url = f"{base_url.rstrip('/')}/embeddings"
            
            with httpx.Client(timeout=60.0) as client:  # 批量请求超时时间更长
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                # 提取所有embedding向量
                if "data" in data and len(data["data"]) > 0:
                    embeddings = [item["embedding"] for item in data["data"]]
                    
                    # 构建响应 - 安全地获取所有参数
                    try:
                        model = request.model if hasattr(request, 'model') else "unknown"
                        usage = data.get("usage", {})
                        
                        llm_response = LLMResponse(
                            content="",  # embedding不返回文本内容
                            model=model,
                            provider="siliconflow",
                            usage=usage,
                            latency_ms=0  # 将在router中设置
                        )
                        
                        # 添加批量embedding字段
                        llm_response.embeddings = embeddings
                        
                        return llm_response
                    except Exception as resp_error:
                        logger.error(f"构建LLMResponse失败: {type(resp_error).__name__}: {str(resp_error)}")
                        raise
                else:
                    raise Exception("API返回的embedding数据为空")
                    
        except Exception as e:
            from ..types import LLMException
            logger.error(f"SiliconFlow批量embedding失败: {str(e)}")
            raise LLMException(
                f"SiliconFlow批量embedding API调用失败: {str(e)}",
                "api_error",
                "siliconflow"
            )
    
    def generate_embedding(self, request) -> 'LLMResponse':
        """
        生成文本嵌入向量（IMPROOVE_GUIDE.md第5.4节要求）
        
        使用SiliconFlow的embedding API
        """
        import httpx
        from ..types import LLMResponse
        
        try:
            # 获取API配置
            api_key = self._get_api_key(request)
            base_url = self._get_base_url(request) or self.default_base_url
            
            # 构建embedding请求（按官方示例格式）
            payload = {
                "model": request.model,
                "input": request.input_text
            }
            
            # Log payload for debugging (mask first 50 chars of input)
            logger.debug(f"Embedding request: model={request.model}, input_len={len(request.input_text) if request.input_text else 0}, input_preview={request.input_text[:50] if request.input_text else 'None'}...")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "SOPilot/1.0"
            }
            
            # 调用embedding API
            url = f"{base_url.rstrip('/')}/embeddings"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=headers)
                
                # 在抛出异常前先尝试获取错误详情
                if response.status_code != 200:
                    error_detail = "Unknown error"
                    try:
                        error_detail = response.text
                    except:
                        pass
                    logger.error(f"SiliconFlow embedding API错误: status={response.status_code}, detail={error_detail}, payload={payload}")
                
                response.raise_for_status()
                
                data = response.json()
                
                # 提取embedding向量
                if "data" in data and len(data["data"]) > 0:
                    embedding = data["data"][0]["embedding"]
                    
                    # 构建响应
                    llm_response = LLMResponse(
                        content="",  # embedding不返回文本内容
                        model=request.model,
                        provider="siliconflow",
                        usage=data.get("usage", {}),
                        latency_ms=0  # 将在router中设置
                    )
                    
                    # 添加embedding字段
                    llm_response.embedding = embedding
                    
                    return llm_response
                else:
                    raise Exception("API返回的embedding数据格式错误")
                    
        except Exception as e:
            logger.error(f"SiliconFlow embedding API调用失败: {e}")
            # 严格按照指南要求：不做兜底，直接抛出异常
            raise RuntimeError(f"SiliconFlow embedding API调用失败: {e}")