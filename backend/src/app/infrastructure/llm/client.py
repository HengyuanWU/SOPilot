#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
from typing import Dict, Any, Optional

from .types import (
	LLMRequest, LLMResponse, LLMClient, LLMException,
	LLMRateLimitException, LLMServerException, LLMNetworkException,
	LLMInvalidRequestException, ProviderName, APIKey,
)
from .middleware import MiddlewareChain, create_default_middleware_chain
from .providers.openai_client import OpenAICompatibleClient, SiliconFlowClient, DeepSeekCompatibleClient
from .balancer import KeyBalancer, BalancerConfig
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class LLMClientFacade:
	def __init__(self,
			 key_balancer: Optional[Any] = None,
			 provider_registry: Optional[Dict[ProviderName, LLMClient]] = None,
			 middleware_chain: Optional[MiddlewareChain] = None,
			 default_config: Optional[Dict[str, Any]] = None):
		self._key_balancer = key_balancer
		self._provider_registry = provider_registry or {}
		self._middleware_chain = middleware_chain
		self._default_config = default_config or {}
		self._initialized = False

	def _ensure_initialized(self) -> None:
		if self._initialized:
			return
		if self._key_balancer is None:
			self._key_balancer = self._create_default_key_balancer()
		if not self._provider_registry:
			self._provider_registry = self._create_default_provider_registry()
		if self._middleware_chain is None:
			self._middleware_chain = create_default_middleware_chain()
		self._initialized = True

	def _create_default_key_balancer(self) -> Any:
		s = get_settings()
		provider_keys = {name: (p.api_keys or []) for name, p in (s.providers or {}).items()}
		balancer_cfg = BalancerConfig(
			strategy_name=s.balancer.strategy_name,
			failure_threshold=s.balancer.failure_threshold,
			circuit_timeout=s.balancer.circuit_timeout,
			recovery_threshold=s.balancer.recovery_threshold,
		)
		return KeyBalancer(provider_keys, balancer_cfg)

	def _create_default_provider_registry(self) -> Dict[ProviderName, LLMClient]:
		return {
			"openai": OpenAICompatibleClient(),
			"siliconflow": SiliconFlowClient(),
			"deepseek": DeepSeekCompatibleClient(),
		}

	def call(self, request: LLMRequest) -> LLMResponse:
		self._ensure_initialized()
		start_time = time.time()
		provider_name = request.get("provider", "openai")
		try:
			self._validate_request(request)
			provider_client = self._get_provider_client(provider_name)
			api_key = self._get_api_key(provider_name)
			response = self._execute_with_middleware(provider_client, request, api_key)
			self._report_success(provider_name, api_key)
			response["latency_ms"] = int((time.time() - start_time) * 1000)
			return response
		except LLMException as e:
			api_key = getattr(e, '_api_key', None)
			if api_key:
				self._report_failure(provider_name, api_key, e)
			raise
		except Exception as e:
			logger.error(f"Unexpected error in LLMClientFacade: {e}", exc_info=True)
			raise LLMException(f"Unexpected error: {str(e)}", provider=provider_name) from e

	def _validate_request(self, request: LLMRequest) -> None:
		for field in ["model", "messages"]:
			if field not in request or not request[field]:
				raise LLMInvalidRequestException(f"Missing required field: {field}", provider=request.get("provider", ""))

	def _get_provider_client(self, provider_name: ProviderName) -> LLMClient:
		if provider_name not in self._provider_registry:
			raise LLMInvalidRequestException(f"Unsupported provider: {provider_name}")
		return self._provider_registry[provider_name]

	def _get_api_key(self, provider_name: ProviderName) -> APIKey:
		api_key = self._key_balancer.get_current_key(provider_name)
		if not api_key:
			raise LLMException(f"No available API key for provider: {provider_name}")
		return api_key

	def _execute_with_middleware(self, client: LLMClient, request: LLMRequest, api_key: APIKey) -> LLMResponse:
		def execute_request():
			try:
				result = client.call(request, api_key)
				if hasattr(result, '_api_key'):
					result._api_key = api_key
				return result
			except LLMException as e:
				e._api_key = api_key
				raise
		wrapped_execute = self._middleware_chain.apply(execute_request)
		return wrapped_execute()

	def _report_success(self, provider_name: ProviderName, api_key: APIKey) -> None:
		self._key_balancer.report_success(provider_name, api_key)

	def _report_failure(self, provider_name: ProviderName, api_key: APIKey, error: LLMException) -> None:
		self._key_balancer.report_failure(provider_name, api_key, error)


def create_default_facade() -> LLMClientFacade:
	return LLMClientFacade()


def llm_call_via_facade(prompt: str, api_type: str = "siliconflow", max_tokens: int = 1024, agent_name: Optional[str] = None) -> str:
	facade = create_default_facade()
	provider_mapping = {"siliconflow": "siliconflow", "sf": "siliconflow", "deepseek": "deepseek", "ds": "deepseek", "openai": "openai"}
	provider = provider_mapping.get(api_type.lower(), "siliconflow")
	s = get_settings()
	p = s.providers.get(provider)
	if p:
		model = p.model
		base_url = p.base_url
		temperature = p.temperature
		timeout = p.timeout
	else:
		model = "Qwen/Qwen3-Coder-30B-A3B-Instruct" if provider == "siliconflow" else "gpt-3.5-turbo"
		base_url = "https://api.siliconflow.cn/v1" if provider == "siliconflow" else None
		temperature = 0.7
		timeout = 300
	request = LLMRequest(
		provider=provider,
		model=model or ("Qwen/Qwen3-Coder-30B-A3B-Instruct" if provider == "siliconflow" else "gpt-3.5-turbo"),
		messages=[{"role": "user", "content": prompt}],
		temperature=temperature,
		max_tokens=max_tokens,
		timeout=timeout,
		base_url=base_url,
	)
	response = facade.call(request)
	return response["content"]


def llm_call(prompt: str, api_type: str = "siliconflow", max_tokens: int = 1024, agent_name: Optional[str] = None) -> str:
	return llm_call_via_facade(prompt, api_type, max_tokens, agent_name)

