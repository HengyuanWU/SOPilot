#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
落盘工具：将运行产物写入 output 目录（遵循 AppSettings.output_dir）。
结构：
- <output_dir>/<run_id>/
  - status.json      # 运行状态（id/status/error/result/updated_at）
  - final.md         # 最终合成内容（如有）
  - kg_section_ids.json  # KG section id 列表（如有）
  - meta.json        # 其他可选元数据
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from app.core.settings import get_settings


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_run_output(run: Dict[str, Any]) -> str:
    """将运行结果落盘，返回目录路径。"""
    settings = get_settings()
    output_root = settings.output_dir or "/app/output"
    run_id = str(run.get("id") or run.get("run_id") or "unknown")
    run_dir = os.path.join(output_root, run_id)
    _ensure_dir(run_dir)

    # 1) status.json（注意不要写入 full 文本）
    status_path = os.path.join(run_dir, "status.json")
    status_payload = {k: run.get(k) for k in ("id", "status", "error", "result", "updated_at")}
    if isinstance(status_payload.get("result"), dict):
        result_copy = dict(status_payload["result"])  # 浅拷贝
        result_copy.pop("final_content_full", None)
        status_payload["result"] = result_copy
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status_payload, f, ensure_ascii=False, indent=2)

    # 2) final.md（可选）
    final_full = None
    if isinstance(run.get("result"), dict):
        res = run.get("result") or {}
        # 优先写入完整内容
        final_full = res.get("final_content_full") or res.get("final_content")
    if isinstance(final_full, str) and final_full.strip():
        with open(os.path.join(run_dir, "final.md"), "w", encoding="utf-8") as f:
            f.write(final_full)

    # 3) kg_section_ids.json（可选）
    result = run.get("result") or {}
    section_ids = result.get("section_ids") if isinstance(result, dict) else None
    section_id = result.get("section_id") if isinstance(result, dict) else None
    if section_id and (not section_ids):
        section_ids = [section_id]
    if section_ids:
        with open(os.path.join(run_dir, "kg_section_ids.json"), "w", encoding="utf-8") as f:
            json.dump({"section_ids": section_ids}, f, ensure_ascii=False, indent=2)

    # 4) meta.json 占位（如需扩展）
    meta = {
        "output_root": output_root,
        "run_dir": run_dir,
    }
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return run_dir

