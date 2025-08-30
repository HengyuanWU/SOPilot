from __future__ import annotations

from typing import Any, Dict

from ..core.settings import AppSettings


def build_legacy_config_from_settings(settings: AppSettings) -> Dict[str, Any]:
    """将 AppSettings 映射为旧版 config/config.py 所期望的配置结构。

    返回字典包含 keys：env/topic/language/num_chapters/llm/balancer/middleware/neo4j 等。
    """
    providers: Dict[str, Any] = {}
    for name, p in (settings.providers or {}).items():
        providers[name] = {
            "base_url": p.base_url,
            "model": p.model,
            "api_keys": list(p.api_keys or []),
            "temperature": p.temperature,
            "max_tokens": p.max_tokens,
            "timeout": p.timeout,
        }

    llm: Dict[str, Any] = {
        "provider": settings.default_provider or "siliconflow",
        "providers": providers,
        "balancer": {
            "strategy": settings.balancer.strategy_name,
            "failure_threshold": settings.balancer.failure_threshold,
            "circuit_timeout": settings.balancer.circuit_timeout,
            "recovery_threshold": settings.balancer.recovery_threshold,
        },
        "middleware": {
            "max_retries": settings.middleware.max_retries,
            "default_timeout": settings.middleware.default_timeout,
            "log_level": settings.middleware.log_level,
            "mask_sensitive": settings.middleware.mask_sensitive,
            "rate_limit": settings.middleware.requests_per_minute,
        },
    }

    neo4j = {
        "uri": settings.neo4j.uri,
        "user": settings.neo4j.user,
        "password": settings.neo4j.password,
        "database": settings.neo4j.database or "neo4j",
    }

    # 占位：topic/language/num_chapters 在运行时由请求体提供
    return {
        "env": settings.env,
        "topic": "",
        "language": "",
        "num_chapters": None,
        "llm": llm,
        "neo4j": neo4j,
        "agents": {},
    }

