from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, List, Optional, Union, Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseModel):
    base_url: Optional[str] = None
    model: str = ""
    api_keys: List[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 300
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None


class BalancerSettings(BaseModel):
    strategy_name: str = "round_robin"
    failure_threshold: int = 5
    circuit_timeout: float = 300.0
    recovery_threshold: int = 2


class MiddlewareSettings(BaseModel):
    max_retries: int = 3
    default_timeout: int = 300
    log_level: str = "INFO"
    mask_sensitive: bool = True
    requests_per_minute: int = 60


class Neo4jSettings(BaseModel):
    uri: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None


class AppSettings(BaseSettings):
    # 基础
    app_name: str = "SOPilot API"
    env: str = "dev"
    debug: bool = True
    # 控制是否使用真实工作流（默认关闭，避免在无 API Key 环境调用外部接口）
    use_real_workflow: bool = True

    # 输出目录
    output_dir: str = "/app/output"

    # LLM 与中间件/均衡器
    default_provider: Optional[str] = None
    providers: Dict[str, ProviderSettings] = Field(default_factory=dict)
    balancer: BalancerSettings = Field(default_factory=BalancerSettings)
    middleware: MiddlewareSettings = Field(default_factory=MiddlewareSettings)

    # Neo4j
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)

    # ENV 优先（允许使用 backend/.env 本地文件）
    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        env_nested_delimiter="__",
        extra="ignore",
    )


def _load_legacy_project_config() -> Dict[str, Any]:
    """已弃用：不再从旧 config 读取，返回空。"""
    return {}


def _merge_env_overrides(base: Dict[str, Any]) -> Dict[str, Any]:
    """对关键字段应用 ENV 覆盖（优先级最高）。"""
    merged = dict(base)
    # 默认 Provider 覆盖
    if os.getenv("APP_DEFAULT_PROVIDER"):
        merged.setdefault("llm", {}).update({"provider": os.getenv("APP_DEFAULT_PROVIDER")})
    # Neo4j 覆盖
    neo4j_env = {
        "uri": os.getenv("NEO4J_URI"),
        "user": os.getenv("NEO4J_USER"),
        "password": os.getenv("NEO4J_PASSWORD"),
        "database": os.getenv("NEO4J_DATABASE"),
    }
    if any(v for v in neo4j_env.values()):
        merged.setdefault("neo4j", {})
        for k, v in neo4j_env.items():
            if v is not None:
                merged["neo4j"][k] = v
    return merged


def _convert_legacy_to_settings_dict(legacy: Dict[str, Any]) -> Dict[str, Any]:
    """将旧配置结构映射为 AppSettings 的数据字典。"""
    result: Dict[str, Any] = {
        "app_name": "SOPilot API",
        "env": legacy.get("env", "dev"),
        "debug": legacy.get("env", "dev") != "prod",
        "default_provider": None,
        "providers": {},
        "balancer": {},
        "middleware": {},
        "neo4j": legacy.get("neo4j", {}),
    }

    llm_cfg = legacy.get("llm", {})
    if llm_cfg:
        result["default_provider"] = llm_cfg.get("provider")
        # providers
        providers = {}
        for name, p in (llm_cfg.get("providers", {}) or {}).items():
            providers[name] = {
                "base_url": p.get("base_url"),
                "model": p.get("model", ""),
                "api_keys": p.get("api_keys", []) or [],
                "temperature": p.get("temperature", 0.7),
                "max_tokens": p.get("max_tokens", 2000),
                "timeout": p.get("timeout", 300),
            }
        result["providers"] = providers

        # balancer
        bl = llm_cfg.get("balancer", {}) or {}
        result["balancer"] = {
            "strategy_name": bl.get("strategy", "round_robin"),
            "failure_threshold": bl.get("failure_threshold", 5),
            "circuit_timeout": bl.get("circuit_timeout", 300.0),
            "recovery_threshold": bl.get("recovery_threshold", 2),
        }
        # middleware
        mw = llm_cfg.get("middleware", {}) or {}
        result["middleware"] = {
            "max_retries": mw.get("max_retries", 3),
            "default_timeout": mw.get("default_timeout", 300),
            "log_level": mw.get("log_level", "INFO"),
            "mask_sensitive": mw.get("mask_sensitive", True),
            "requests_per_minute": int(mw.get("rate_limit", mw.get("requests_per_minute", 60))),
        }
    return result


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """ENV 优先 + 兼容旧配置，生成统一 Settings。"""
    # 1) 旧配置（已包含部分 ENV 注入，如 API keys）
    legacy_raw = _load_legacy_project_config()
    legacy_raw = _merge_env_overrides(legacy_raw)
    legacy_mapped = _convert_legacy_to_settings_dict(legacy_raw)

    # 2) 读取 ENV（APP_* 前缀）
    env_settings = AppSettings()

    # 3) 合并（ENV 优先）：以 env_settings 中非空值覆盖 legacy_mapped
    merged: Dict[str, Any] = legacy_mapped.copy()
    if env_settings.default_provider:
        merged["default_provider"] = env_settings.default_provider
    # 覆盖 neo4j
    if env_settings.neo4j and any([
        env_settings.neo4j.uri, env_settings.neo4j.user,
        env_settings.neo4j.password, env_settings.neo4j.database
    ]):
        merged["neo4j"] = env_settings.neo4j.model_dump(exclude_none=True)
    # 允许通过 ENV 覆盖 middleware 的部分字段
    merged["middleware"].update(env_settings.middleware.model_dump(exclude_defaults=True, exclude_none=True))
    # 允许通过 ENV 覆盖 balancer 的部分字段
    merged["balancer"].update(env_settings.balancer.model_dump(exclude_defaults=True, exclude_none=True))

    # 4) 合并额外 ENV 控制项
    merged["use_real_workflow"] = bool(env_settings.use_real_workflow)

    # 5) 返回标准化的 AppSettings
    return AppSettings.model_validate(merged)


def settings_diagnostics() -> Dict[str, Any]:
    """生成运行配置简要诊断信息。"""
    s = get_settings()
    providers = {name: {
        "model": p.model,
        "api_keys_count": len(p.api_keys or []),
        "base_url": p.base_url,
    } for name, p in (s.providers or {}).items()}
    return {
        "env": s.env,
        "default_provider": s.default_provider,
        "use_real_workflow": s.use_real_workflow,
        "output_dir": s.output_dir,
        "providers": providers,
        "neo4j": {
            "uri": s.neo4j.uri,
            "database": s.neo4j.database,
        }
    }

