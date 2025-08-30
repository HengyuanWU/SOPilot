#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import TypedDict, Protocol, Dict, List, Any, Optional, Union
from abc import abstractmethod


class LLMRequest(TypedDict, total=False):
	provider: str
	model: str
	messages: List[Dict[str, str]]
	temperature: float
	max_tokens: int
	timeout: int
	base_url: Optional[str]
	top_p: Optional[float]
	frequency_penalty: Optional[float]
	presence_penalty: Optional[float]
	stop: Optional[Union[str, List[str]]]


class LLMResponse(TypedDict, total=False):
	content: str
	provider: str
	model: str
	latency_ms: int
	usage: Optional[Dict[str, Any]]
	finish_reason: Optional[str]
	request_id: Optional[str]


class LLMException(Exception):
	def __init__(self, message: str, provider: str = "", model: str = "", original_error: Optional[Exception] = None):
		super().__init__(message)
		self.provider = provider
		self.model = model
		self.original_error = original_error


class LLMRateLimitException(LLMException):
	def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
		super().__init__(message, **kwargs)
		self.retry_after = retry_after


class LLMServerException(LLMException):
	def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
		super().__init__(message, **kwargs)
		self.status_code = status_code


class LLMNetworkException(LLMException):
	pass


class LLMInvalidRequestException(LLMException):
	def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
		super().__init__(message, **kwargs)
		self.status_code = status_code


class LLMClient(Protocol):
	@abstractmethod
	def call(self, request: LLMRequest, api_key: str) -> LLMResponse: ...

	@abstractmethod
	def validate_request(self, request: LLMRequest) -> bool: ...


ProviderName = str
ModelName = str
APIKey = str

