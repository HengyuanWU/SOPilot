#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一并发配置（纯本地实现，无旧依赖）。"""

from __future__ import annotations

import os
from typing import Dict


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _build_base_config() -> Dict:
    return {
        "writer": {
            "max_workers": _int_env("WRITER_MAX_WORKERS", 50),
            "timeout": _int_env("WRITER_TIMEOUT", 120),
            "chunk_size": _int_env("WRITER_CHUNK_SIZE", 10),
            "retry_count": _int_env("WRITER_RETRY_COUNT", 3),
        },
        "qa_generator": {
            "max_workers": _int_env("QA_MAX_WORKERS", 50),
            "timeout": _int_env("QA_TIMEOUT", 120),
            "chunk_size": _int_env("QA_CHUNK_SIZE", 10),
            "retry_count": _int_env("QA_RETRY_COUNT", 3),
        },
        "kg_builder": {
            "max_workers": _int_env("KG_MAX_WORKERS", 50),
            "timeout": _int_env("KG_TIMEOUT", 120),
            "chunk_size": _int_env("KG_CHUNK_SIZE", 10),
            "retry_count": _int_env("KG_RETRY_COUNT", 3),
        },
        "researcher": {
            "max_workers": _int_env("RESEARCHER_MAX_WORKERS", 50),
            "timeout": _int_env("RESEARCHER_TIMEOUT", 120),
            "chunk_size": _int_env("RESEARCHER_CHUNK_SIZE", 10),
            "retry_count": _int_env("RESEARCHER_RETRY_COUNT", 3),
        },
        "validator": {
            "max_workers": _int_env("VALIDATOR_MAX_WORKERS", 50),
            "timeout": _int_env("VALIDATOR_TIMEOUT", 120),
            "chunk_size": _int_env("VALIDATOR_CHUNK_SIZE", 10),
            "retry_count": _int_env("VALIDATOR_RETRY_COUNT", 3),
            "pass_threshold": float(os.getenv("VALIDATOR_PASS_THRESHOLD", "7.0")),
            "max_rewrite_attempts": _int_env("VALIDATOR_MAX_REWRITE_ATTEMPTS", 1),
        },
        "global": {
            "max_total_workers": _int_env("GLOBAL_MAX_WORKERS", 200),
            "io_bound_multiplier": _int_env("GLOBAL_IO_MULTIPLIER", 2),
            "cpu_bound_multiplier": _int_env("GLOBAL_CPU_MULTIPLIER", 1),
            "enable_process_pool": os.getenv("GLOBAL_ENABLE_PROCESS_POOL", "false").lower() == "true",
            "process_pool_workers": _int_env("GLOBAL_PROCESS_POOL_WORKERS", 4),
        },
    }


class _CC:
    def __init__(self, cfg: Dict):
        self._cfg = cfg

    def get_agent_config(self, agent_name: str) -> Dict:
        return dict(self._cfg.get(agent_name, {}))

    def get_timeout(self, agent_name: str) -> int:
        return int(self._cfg.get(agent_name, {}).get("timeout", 300))

    def get_retry_count(self, agent_name: str) -> int:
        return int(self._cfg.get(agent_name, {}).get("retry_count", 3))

    def get_chunk_size(self, agent_name: str) -> int:
        return int(self._cfg.get(agent_name, {}).get("chunk_size", 10))

    def create_thread_pool(self, agent_name: str, task_count: int):
        import concurrent.futures as _f

        max_workers = min(max(1, task_count or 1), int(self._cfg.get(agent_name, {}).get("max_workers", 50)))
        return _f.ThreadPoolExecutor(max_workers=max_workers)


def get_concurrency_config(high_performance: bool = False) -> Dict:
    base = _build_base_config()
    # 简单高性能版：各主要 agent 翻倍
    if high_performance:
        for k in ("writer", "qa_generator", "kg_builder", "researcher", "validator"):
            base[k]["max_workers"] = max(base[k]["max_workers"], 100)
            base[k]["timeout"] = max(base[k]["timeout"], 600)
    return {
        "writer": _CC(base).get_agent_config("writer"),
        "qa_generator": _CC(base).get_agent_config("qa_generator"),
        "kg_builder": _CC(base).get_agent_config("kg_builder"),
        "researcher": _CC(base).get_agent_config("researcher"),
        "validator": _CC(base).get_agent_config("validator"),
        "global": base.get("global", {}),
        # 暴露原方法，供现有代码继续使用
        "get_timeout": _CC(base).get_timeout,
        "get_retry_count": _CC(base).get_retry_count,
        "get_chunk_size": _CC(base).get_chunk_size,
        "create_thread_pool": _CC(base).create_thread_pool,
    }


# 兼容现有用法（对象风格访问）
_default = _CC(_build_base_config())
_high = _CC(_build_base_config())


default_concurrency_config = _default
high_concurrency_config = _high

