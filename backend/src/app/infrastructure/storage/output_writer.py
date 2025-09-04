#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
落盘工具：将运行产物写入 output 目录（遵循 AppSettings.output_dir）。
结构（按 IMPROOVE_GUIDE.md 标准）：
- <output_dir>/<run_id>/
  - book.md                 # 合并后的 Markdown
  - book.json               # 结构化元数据（章节树、统计）
  - qa.json                 # QA 对
  - kg_section_ids.json     # 小节 ID 列表
  - book_id.txt             # 整书图谱 ID
  - logs.ndjson             # 运行日志（SSE 同步写入）
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from ...core.settings import get_settings


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_run_output(run: Dict[str, Any]) -> str:
    """将运行结果落盘，返回目录路径。按照 IMPROOVE_GUIDE.md 标准格式。"""
    settings = get_settings()
    output_root = settings.output_dir or "/app/output"
    run_id = str(run.get("id") or run.get("run_id") or "unknown")
    run_dir = os.path.join(output_root, run_id)
    _ensure_dir(run_dir)

    result = run.get("result") or {}

    # 1) book.md - 合并后的 Markdown
    final_full = None
    if isinstance(result, dict):
        final_full = result.get("final_content_full") or result.get("final_content")
    if isinstance(final_full, str) and final_full.strip():
        with open(os.path.join(run_dir, "book.md"), "w", encoding="utf-8") as f:
            f.write(final_full)

    # 2) book.json - 结构化元数据（章节树、统计）
    book_metadata = {
        "run_id": run.get("id"),
        "status": run.get("status"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "workflow_id": result.get("workflow_id"),
        "workflow_params": result.get("workflow_params"),
        "processing_stats": result.get("processing_stats"),
        "chapter_count": result.get("chapter_count"),
        "section_count": len(result.get("section_ids", [])) if result.get("section_ids") else 0,
    }
    with open(os.path.join(run_dir, "book.json"), "w", encoding="utf-8") as f:
        json.dump(book_metadata, f, ensure_ascii=False, indent=2)

    # 3) qa.json - QA 对（如果有）
    qa_data = result.get("qa_pairs") or result.get("questions") or []
    if qa_data:
        with open(os.path.join(run_dir, "qa.json"), "w", encoding="utf-8") as f:
            json.dump({"qa_pairs": qa_data}, f, ensure_ascii=False, indent=2)

    # 4) kg_section_ids.json - 小节 ID 列表
    section_ids = result.get("section_ids") if isinstance(result, dict) else None
    section_id = result.get("section_id") if isinstance(result, dict) else None
    if section_id and (not section_ids):
        section_ids = [section_id]
    if section_ids:
        with open(os.path.join(run_dir, "kg_section_ids.json"), "w", encoding="utf-8") as f:
            json.dump({"section_ids": section_ids}, f, ensure_ascii=False, indent=2)

    # 5) book_id.txt - 整书图谱 ID
    book_id = result.get("book_id")
    if book_id:
        with open(os.path.join(run_dir, "book_id.txt"), "w", encoding="utf-8") as f:
            f.write(str(book_id))

    # 6) logs.ndjson - 将会在 stream 过程中同步写入
    # 这里只创建空文件确保存在
    logs_path = os.path.join(run_dir, "logs.ndjson")
    if not os.path.exists(logs_path):
        with open(logs_path, "w", encoding="utf-8") as f:
            pass  # 创建空文件

    return run_dir


def append_run_log(run_id: str, log_entry: Dict[str, Any]) -> None:
    """追加运行日志到 logs.ndjson 文件。"""
    settings = get_settings()
    output_root = settings.output_dir or "/app/output"
    run_dir = os.path.join(output_root, str(run_id))
    logs_path = os.path.join(run_dir, "logs.ndjson")
    
    # 确保目录存在
    _ensure_dir(run_dir)
    
    # 追加 NDJSON 格式的日志
    with open(logs_path, "a", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')


def get_run_artifacts_dir(run_id: str) -> str:
    """获取运行产物目录路径。"""
    settings = get_settings()
    output_root = settings.output_dir or "/app/output"
    return os.path.join(output_root, str(run_id))


def list_run_artifacts(run_id: str) -> list[Dict[str, Any]]:
    """列出运行产物文件。"""
    run_dir = get_run_artifacts_dir(run_id)
    if not os.path.exists(run_dir):
        return []
    
    artifacts = []
    for filename in os.listdir(run_dir):
        filepath = os.path.join(run_dir, filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            artifacts.append({
                "name": filename,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "type": _get_file_type(filename),
            })
    
    return sorted(artifacts, key=lambda x: x["name"])


def _get_file_type(filename: str) -> str:
    """根据文件名判断文件类型。"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ""
    type_mapping = {
        "md": "markdown",
        "json": "json", 
        "txt": "text",
        "ndjson": "logs",
    }
    return type_mapping.get(ext, "unknown")

