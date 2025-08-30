#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import threading
import time
from typing import Dict, List, Optional, Any

from .types import ProviderName, APIKey, LLMException

logger = logging.getLogger(__name__)


class KeyStatus:
	ACTIVE = "active"
	FAILED = "failed"
	CIRCUIT_OPEN = "circuit_open"
	CIRCUIT_HALF_OPEN = "circuit_half_open"


class KeyStats:
	def __init__(self, key_id: str):
		self.key_id = key_id
		self.total_requests = 0
		self.successful_requests = 0
		self.failed_requests = 0
		self.consecutive_failures = 0
		self.last_success_time: Optional[float] = None
		self.last_failure_time: Optional[float] = None
		self.circuit_open_time: Optional[float] = None
		self.status = KeyStatus.ACTIVE

	@property
	def success_rate(self) -> float:
		if self.total_requests == 0:
			return 1.0
		return self.successful_requests / self.total_requests


class BalancerConfig:
	def __init__(self, strategy_name: str = "round_robin", failure_threshold: int = 5, circuit_timeout: float = 300.0, recovery_threshold: int = 2):
		self.strategy_name = strategy_name
		self.failure_threshold = failure_threshold
		self.circuit_timeout = circuit_timeout
		self.recovery_threshold = recovery_threshold


class RoundRobinStrategy:
	def __init__(self):
		self._counter = 0
		self._lock = threading.Lock()

	def select_key(self, available_keys: List[APIKey], key_stats: Dict[APIKey, KeyStats]) -> Optional[APIKey]:
		if not available_keys:
			return None
		with self._lock:
			key = available_keys[self._counter % len(available_keys)]
			self._counter += 1
			return key


def create_strategy(name: str) -> RoundRobinStrategy:
	return RoundRobinStrategy()


class KeyBalancer:
	def __init__(self, provider_keys: Optional[Dict[ProviderName, List[APIKey]]] = None, config: Optional[BalancerConfig] = None, strategy: Optional[Any] = None):
		self.provider_keys = provider_keys or {}
		self.config = config or BalancerConfig()
		self.strategy = strategy or create_strategy(self.config.strategy_name)
		self._lock = threading.RLock()
		self._key_stats: Dict[ProviderName, Dict[APIKey, KeyStats]] = {}
		self._initialize_stats()

	def _initialize_stats(self) -> None:
		with self._lock:
			for provider, keys in self.provider_keys.items():
				self._key_stats.setdefault(provider, {})
				for key in keys:
					if key not in self._key_stats[provider]:
						self._key_stats[provider][key] = KeyStats(key_id=self._mask_key(key))

	def add_provider_keys(self, provider: ProviderName, keys: List[APIKey]) -> None:
		with self._lock:
			self.provider_keys.setdefault(provider, [])
			self._key_stats.setdefault(provider, {})
			for key in keys:
				if key not in self.provider_keys[provider]:
					self.provider_keys[provider].append(key)
					self._key_stats[provider][key] = KeyStats(key_id=self._mask_key(key))

	def get_current_key(self, provider: ProviderName) -> Optional[APIKey]:
		with self._lock:
			if provider not in self.provider_keys:
				logger.warning(f"No keys configured for provider: {provider}")
				return None
			available = self._get_available_keys(provider)
			if not available:
				return None
			return self.strategy.select_key(available, self._key_stats[provider])

	def report_success(self, provider: ProviderName, key: APIKey) -> None:
		with self._lock:
			stats = self._key_stats.get(provider, {}).get(key)
			if not stats:
				return
			stats.total_requests += 1
			stats.successful_requests += 1
			stats.consecutive_failures = 0
			stats.last_success_time = time.time()
			if stats.status in (KeyStatus.FAILED, KeyStatus.CIRCUIT_HALF_OPEN):
				stats.status = KeyStatus.ACTIVE

	def report_failure(self, provider: ProviderName, key: APIKey, error: Optional[LLMException] = None) -> None:
		with self._lock:
			stats = self._key_stats.get(provider, {}).get(key)
			if not stats:
				return
			stats.total_requests += 1
			stats.failed_requests += 1
			stats.consecutive_failures += 1
			stats.last_failure_time = time.time()
			if stats.consecutive_failures >= self.config.failure_threshold:
				stats.status = KeyStatus.CIRCUIT_OPEN
				stats.circuit_open_time = time.time()
			else:
				stats.status = KeyStatus.FAILED

	def _get_available_keys(self, provider: ProviderName) -> List[APIKey]:
		available: List[APIKey] = []
		now = time.time()
		for key in self.provider_keys.get(provider, []):
			stats = self._key_stats[provider][key]
			if stats.status == KeyStatus.CIRCUIT_OPEN and stats.circuit_open_time and (now - stats.circuit_open_time) >= self.config.circuit_timeout:
				stats.status = KeyStatus.CIRCUIT_HALF_OPEN
			available.append(key)
		return available

	def _mask_key(self, key: APIKey) -> str:
		return "****" if len(key) <= 8 else f"{key[:4]}...{key[-4:]}"

