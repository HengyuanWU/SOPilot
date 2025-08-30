#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import logging
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.exceptions import LangChainException
import requests

from ..types import (
	LLMRequest, LLMResponse, LLMClient, LLMException,
	LLMRateLimitException, LLMServerException, LLMNetworkException,
	LLMInvalidRequestException,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
	def __init__(self, default_config: Optional[Dict[str, Any]] = None):
		self.default_config = default_config or {}
		self.supported_params = {"model", "temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty", "stop"}

	def call(self, request: LLMRequest, api_key: str) -> LLMResponse:
		start_time = time.time()
		try:
			self.validate_request(request)
			chat_client = self._create_chat_client(request, api_key)
			messages = self._convert_messages(request["messages"])
			response = chat_client.invoke(messages)
			return LLMResponse(
				content=response.content,
				provider=request.get("provider", "openai"),
				model=request["model"],
				latency_ms=int((time.time() - start_time) * 1000),
				usage=getattr(response, 'usage_metadata', None),
				finish_reason=getattr(response, 'finish_reason', None),
				request_id=getattr(response, 'response_metadata', {}).get('request_id')
			)
		except Exception as e:
			raise self._convert_exception(e, request.get("provider", "openai"))

	def validate_request(self, request: LLMRequest) -> bool:
		if not request.get("model"):
			raise LLMInvalidRequestException("Missing required field: model")
		if not request.get("messages"):
			raise LLMInvalidRequestException("Missing required field: messages")
		messages = request["messages"]
		if not isinstance(messages, list) or not messages:
			raise LLMInvalidRequestException("Messages must be a non-empty list")
		for i, msg in enumerate(messages):
			if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
				raise LLMInvalidRequestException(f"Invalid message at index {i}")
			if msg["role"] not in ["system", "user", "assistant"]:
				raise LLMInvalidRequestException(f"Unsupported message role: {msg['role']}")
		if "temperature" in request:
			temp = request["temperature"]
			if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
				raise LLMInvalidRequestException("Temperature must be between 0 and 2")
		if "max_tokens" in request:
			max_tokens = request["max_tokens"]
			if not isinstance(max_tokens, int) or max_tokens <= 0:
				raise LLMInvalidRequestException("max_tokens must be a positive integer")
		return True

	def _create_chat_client(self, request: LLMRequest, api_key: str) -> ChatOpenAI:
		config: Dict[str, Any] = {
			"api_key": api_key,
			"model": request["model"],
			"temperature": request.get("temperature", 0.7),
			"max_tokens": request.get("max_tokens", 1024),
			"request_timeout": request.get("timeout", 300),
		}
		if request.get("base_url"):
			config["base_url"] = request["base_url"]
		for param in self.supported_params:
			if param in request and param not in config:
				config[param] = request[param]
		return ChatOpenAI(**config)

	def _convert_messages(self, messages: List[Dict[str, str]]):
		converted = []
		for msg in messages:
			role = msg["role"]
			content = msg["content"]
			if role == "system":
				converted.append(SystemMessage(content=content))
			elif role == "user":
				converted.append(HumanMessage(content=content))
			elif role == "assistant":
				converted.append(AIMessage(content=content))
			else:
				raise LLMInvalidRequestException(f"Unsupported message role: {role}")
		return converted

	def _convert_exception(self, exception: Exception, provider: str) -> LLMException:
		error_msg = str(exception)
		if isinstance(exception, requests.exceptions.Timeout):
			return LLMNetworkException(f"Request timeout: {error_msg}", provider=provider, original_error=exception)
		elif isinstance(exception, requests.exceptions.ConnectionError):
			return LLMNetworkException(f"Connection error: {error_msg}", provider=provider, original_error=exception)
		elif isinstance(exception, requests.exceptions.RequestException):
			return LLMNetworkException(f"Network error: {error_msg}", provider=provider, original_error=exception)
		elif isinstance(exception, LangChainException):
			if "rate limit" in error_msg.lower() or "429" in error_msg:
				return LLMRateLimitException(error_msg, provider=provider, original_error=exception)
			elif "401" in error_msg or "403" in error_msg:
				return LLMInvalidRequestException(f"Authentication error: {error_msg}", provider=provider, original_error=exception)
			elif "400" in error_msg:
				return LLMInvalidRequestException(f"Bad request: {error_msg}", provider=provider, original_error=exception)
			elif any(code in error_msg for code in ["500", "502", "503"]):
				return LLMServerException(f"Server error: {error_msg}", provider=provider, original_error=exception)
			else:
				return LLMException(f"LangChain error: {error_msg}", provider=provider, original_error=exception)
		else:
			if "rate limit" in error_msg.lower() or "429" in error_msg:
				return LLMRateLimitException(error_msg, provider=provider, original_error=exception)
			elif any(s in error_msg.lower() for s in ["timeout", "connection"]):
				return LLMNetworkException(error_msg, provider=provider, original_error=exception)
			elif any(code in error_msg for code in ["400", "401", "403"]):
				return LLMInvalidRequestException(error_msg, provider=provider, original_error=exception)
			elif any(code in error_msg for code in ["500", "502", "503"]):
				return LLMServerException(error_msg, provider=provider, original_error=exception)
			else:
				return LLMException(error_msg, provider=provider, original_error=exception)


class SiliconFlowClient(OpenAICompatibleClient):
	def __init__(self, default_config: Optional[Dict[str, Any]] = None):
		super().__init__(default_config)
		self.default_config.update({"base_url": "https://api.siliconflow.cn/v1", "model": "Qwen/Qwen3-Coder-30B-A3B-Instruct"})


class DeepSeekCompatibleClient(OpenAICompatibleClient):
	def __init__(self, default_config: Optional[Dict[str, Any]] = None):
		super().__init__(default_config)
		self.default_config.update({"base_url": "https://api.deepseek.com/v1", "model": "deepseek-coder"})

