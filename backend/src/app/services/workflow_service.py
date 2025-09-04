from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from ..core.settings import get_settings
from ..infrastructure.storage.output_writer import append_run_log, write_run_output


# 内存运行表（阶段5最小实现；后续可替换为持久化）
RUNS: Dict[str, Dict[str, Any]] = {}
RUN_LOGS: Dict[str, asyncio.Queue[str]] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def create_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """创建运行并异步启动（支持多工作流）。"""
    run_id = str(uuid.uuid4())
    workflow_id = payload.get("workflow_id", "textbook")  # 默认为textbook保持兼容性
    
    RUNS[run_id] = {
        "id": run_id,
        "status": "pending",
        "created_at": _now_ms(),
        "updated_at": _now_ms(),
        "topic": payload.get("topic"),
        "language": payload.get("language"),
        "chapter_count": payload.get("chapter_count"),
        "workflow_id": workflow_id,
        "workflow_params": payload.get("workflow_params", {}),
        "error": None,
        "result": None,
    }
    RUN_LOGS[run_id] = asyncio.Queue()

    # 启动后台任务（根据配置决定是模拟还是实际工作流）
    settings = get_settings()
    if settings.use_real_workflow:
        asyncio.get_event_loop().create_task(_run_real_workflow(run_id))
    else:
        asyncio.get_event_loop().create_task(_run_simulated(run_id))
    return RUNS[run_id]


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return RUNS.get(run_id)


async def _run_simulated(run_id: str) -> None:
    """模拟执行不同工作流并推送日志。"""
    run = RUNS.get(run_id)
    if not run:
        return
    settings = get_settings()
    workflow_id = run.get("workflow_id", "textbook")

    async def log(msg: str) -> None:
        timestamp = _now_ms()
        # 发送到SSE流
        await RUN_LOGS[run_id].put(msg)
        # 同时写入文件
        try:
            append_run_log(run_id, {
                "timestamp": timestamp,
                "message": msg,
                "level": "info" if "[info]" in msg else "error" if "[error]" in msg else "debug"
            })
        except Exception as e:
            # 日志写入失败不应该影响主流程
            pass

    try:
        run["status"] = "running"
        run["updated_at"] = _now_ms()
        await log(f"[info] run {run_id} started | workflow={workflow_id} | provider={settings.default_provider or 'unset'} | mode=simulated")

        await asyncio.sleep(0.3)
        await log(f"[info] initializing {workflow_id} workflow...")

        await asyncio.sleep(0.5)
        
        # 根据工作流类型模拟不同的执行步骤
        if workflow_id == "textbook":
            await log("[info] executing planner → researcher → writer → qa → kg → merger (simulated)")
        elif workflow_id == "quiz_maker":
            await log("[info] executing question_generator → formatter (simulated)")
        else:
            await log(f"[info] executing {workflow_id} workflow steps (simulated)")

        await asyncio.sleep(0.4)
        await log("[info] finalizing...")

        # 根据工作流类型生成不同的结果
        if workflow_id == "textbook":
            run["result"] = {
                "message": "教材生成完成",
                "workflow": workflow_id,
                "chapters_generated": run.get("chapter_count", 8),
                "topic": run.get("topic", "示例主题")
            }
        elif workflow_id == "quiz_maker":
            run["result"] = {
                "message": "问答生成完成", 
                "workflow": workflow_id,
                "questions_generated": run.get("workflow_params", {}).get("question_count", 10),
                "topic": run.get("topic", "示例主题")
            }
        else:
            run["result"] = {
                "message": f"{workflow_id} 工作流执行完成",
                "workflow": workflow_id,
                "topic": run.get("topic", "示例主题")
            }
            
        run["status"] = "succeeded"
        run["updated_at"] = _now_ms()
        await log(f"[done] {workflow_id} workflow succeeded")
        
        # 写入产物到磁盘
        try:
            write_run_output(run)
            await log("[info] artifacts written to disk")
        except Exception as e:
            await log(f"[warning] failed to write artifacts: {e}")
    except Exception as exc:  # noqa: BLE001
        run["status"] = "failed"
        run["error"] = str(exc)
        run["updated_at"] = _now_ms()
        await log(f"[error] {exc}")
    finally:
        # 结束标识
        await RUN_LOGS[run_id].put("__EOF__")


async def stream_run(run_id: str) -> AsyncGenerator[str, None]:
    """SSE 事件流（text/event-stream）。"""
    queue = RUN_LOGS.get(run_id)
    if queue is None:
        # 若不存在，立即结束
        yield "event: end\n" "data: not-found\n\n"
        return
    while True:
        item = await queue.get()
        if item == "__EOF__":
            yield "event: end\n" "data: done\n\n"
            return
        # 标准 SSE 帧
        yield f"event: log\n" f"data: {item}\n\n"


async def _run_real_workflow(run_id: str) -> None:
    """真实工作流执行：线程池中运行 TextbookApp，流式回传关键日志。"""
    run = RUNS.get(run_id)
    if not run:
        return
    settings = get_settings()

    async def log(msg: str) -> None:
        timestamp = _now_ms()
        # 发送到SSE流
        await RUN_LOGS[run_id].put(msg)
        # 同时写入文件
        try:
            append_run_log(run_id, {
                "timestamp": timestamp,
                "message": msg,
                "level": "info" if "[info]" in msg else "error" if "[error]" in msg else "debug"
            })
        except Exception as e:
            # 日志写入失败不应该影响主流程
            pass

    try:
        run["status"] = "running"
        run["updated_at"] = _now_ms()
        await log(f"[info] run {run_id} started | provider={settings.default_provider or 'unset'} | mode=real")

        # 在线程池中执行以避免阻塞事件循环
        loop = asyncio.get_event_loop()
        queue = RUN_LOGS[run_id]

        def _execute_workflow() -> Dict[str, Any]:
            # 动态获取工作流实例
            from ..domain.workflows.registry import get_workflow
            from .config_service import build_legacy_config_from_settings
            from ..core.progress_manager import progress_manager

            workflow_id = run.get("workflow_id", "textbook")
            workflow_params = run.get("workflow_params", {})
            
            try:
                # 使用工作流注册系统获取工作流实例
                workflow = get_workflow(workflow_id)
            except ValueError as e:
                raise RuntimeError(f"Unknown workflow: {workflow_id}") from e

            # 准备初始状态
            topic = run.get("topic") or "未命名"
            language = run.get("language") or "中文"
            
            # 构建工作流特定的初始状态
            initial_state = {
                "topic": topic,
                "language": language,
                "thread_id": str(uuid.uuid4()),
                **workflow_params
            }
            
            # 对于textbook工作流，添加特定参数
            if workflow_id == "textbook":
                from ..domain.state.textbook_state import TextbookState
                # 用 AppSettings 构造与旧实现兼容的配置结构
                config = build_legacy_config_from_settings(settings)
                
                chapter_count = int(run.get("chapter_count") or 8)
                initial_state.update({
                    "num_chapters": chapter_count,
                    "chapter_count": chapter_count,
                    "config": config,
                })
            
            # 其他工作流可以根据需要添加特定参数处理
            # 注册进度事件回调，将事件转发到 SSE
            def on_event(evt: str, data: Dict[str, Any]) -> None:
                try:
                    msg = f"[progress] {evt} | {data}"
                    # 将消息安全地投递到 asyncio 队列（切回事件循环线程）
                    loop.call_soon_threadsafe(queue.put_nowait, msg)
                except Exception:
                    # 不影响主流程
                    return

            progress_manager.set_event_callback(on_event)
            try:
                return workflow.execute(initial_state)
            finally:
                progress_manager.set_event_callback(None)

        await log("[info] initializing workflow...")
        result = await loop.run_in_executor(None, _execute_workflow)

        # 成功判定：无 error 即视为成功；否则抛出错误
        if result is None or result.get("error"):
            raise RuntimeError(result.get("error") or "workflow failed")

        # 透传 section_id(s) 和 book_id 供前端与后续查询使用
        section_ids = result.get("section_ids") or []
        if isinstance(section_ids, str):
            section_ids = [section_ids]
        first_section_id = section_ids[0] if section_ids else None

        # B1方案：获取book_id
        book_id = result.get("book_id")

        full_final_content = result.get("final_content")
        run["result"] = {
            "final_content_full": full_final_content,  # 保存完整内容用于写入文件
            "final_content": True if isinstance(full_final_content, str) and full_final_content else None,
            "section_id": first_section_id,
            "section_ids": section_ids or None,
            "book_id": book_id,  # B1方案新增
            "processing_stats": result.get("processing_stats"),
            "workflow_id": run.get("workflow_id"),
            "workflow_params": run.get("workflow_params"),
        }
        run["status"] = "succeeded"
        run["updated_at"] = _now_ms()
        await log("[done] succeeded")
        
        # 写入产物到磁盘
        try:
            write_run_output(run)
            await log("[info] artifacts written to disk")
        except Exception as e:
            await log(f"[warning] failed to write artifacts: {e}")
    except Exception as exc:  # noqa: BLE001
        run["status"] = "failed"
        run["error"] = str(exc)
        run["updated_at"] = _now_ms()
        await log(f"[error] {exc}")
    finally:
        await RUN_LOGS[run_id].put("__EOF__")

