#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
import random
import functools
from typing import Callable, Dict, Any, Optional, List

from .types import (
	LLMRequest, LLMResponse, LLMException,
	LLMRateLimitException, LLMServerException, LLMNetworkException,
)

logger = logging.getLogger(__name__)


class RetryMiddleware:
	def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0, exponential_base: float = 2.0, jitter: bool = True):
		self.max_retries = max_retries
		self.base_delay = base_delay
		self.max_delay = max_delay
		self.exponential_base = exponential_base
		self.jitter = jitter

	def __call__(self, func: Callable) -> Callable:
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			last_exception = None
			for attempt in range(self.max_retries + 1):
				try:
					return func(*args, **kwargs)
				except Exception as e:
					last_exception = e
					if not isinstance(e, (LLMNetworkException, LLMServerException, LLMRateLimitException)):
						raise
					if attempt == self.max_retries:
						raise
					delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
					if self.jitter:
						delay *= (0.5 + random.random() * 0.5)
					logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
					time.sleep(delay)
			raise last_exception
		return wrapper


class TimeoutMiddleware:
	def __init__(self, default_timeout: int = 300):
		self.default_timeout = default_timeout

	def __call__(self, func: Callable) -> Callable:
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			return func(*args, **kwargs)
		return wrapper


class LoggingMiddleware:
	def __init__(self, log_level: int = logging.INFO, log_request: bool = True, log_response: bool = True, log_errors: bool = True, mask_sensitive: bool = True):
		self.log_level = log_level
		self.log_request = log_request
		self.log_response = log_response
		self.log_errors = log_errors
		self.mask_sensitive = mask_sensitive

	def __call__(self, func: Callable) -> Callable:
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			start = time.time()
			if self.log_request and logger.isEnabledFor(self.log_level):
				if args and isinstance(args[0], dict):
					req = args[0]
					logger.log(self.log_level, f"LLM request started: provider={req.get('provider')}, model={req.get('model')}")
			try:
				result = func(*args, **kwargs)
				if self.log_response and logger.isEnabledFor(self.log_level):
					duration = int((time.time() - start) * 1000)
					logger.log(self.log_level, f"LLM request completed in {duration}ms")
				return result
			except Exception as e:
				if self.log_errors:
					duration = int((time.time() - start) * 1000)
					logger.error(f"LLM request failed in {duration}ms: {e}")
				raise
		return wrapper


class MiddlewareChain:
	def __init__(self, middlewares: Optional[List] = None):
		self.middlewares = middlewares or []

	def add(self, middleware) -> 'MiddlewareChain':
		self.middlewares.append(middleware)
		return self

	def apply(self, func: Callable) -> Callable:
		result = func
		for middleware in reversed(self.middlewares):
			result = middleware(result)
		return result


def create_default_middleware_chain() -> MiddlewareChain:
	return MiddlewareChain([
		LoggingMiddleware(),
		TimeoutMiddleware(),
		RetryMiddleware(),
	])

