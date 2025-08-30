#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度管理器 - 用于展示工作流进度和统计时间（迁移自 core.progress_manager）
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class ProgressManager:
	def __init__(self):
		self.start_time = None
		self.stage_times = {}
		self.current_stage = None
		self.stage_start_time = None
		self.total_stages = 0
		self.completed_stages = 0
		self.stage_details = {}
		self.event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None

	def start_workflow(self, total_stages: int = 4):
		self.start_time = time.time()
		self.total_stages = total_stages
		self.completed_stages = 0
		self.stage_times = {}
		self.stage_details = {}
		self._emit("workflow_start", {"total_stages": total_stages})

	def start_stage(self, stage_name: str, stage_description: str = ""):
		if self.stage_start_time:
			self.end_stage()
		self.current_stage = stage_name
		self.stage_start_time = time.time()
		self.stage_details[stage_name] = stage_description
		self._emit("stage_start", {"stage": stage_name, "description": stage_description, "index": self.completed_stages + 1, "total": self.total_stages})

	def update_stage_progress(self, progress_info: str):
		if self.current_stage:
			self._emit("stage_progress", {"stage": self.current_stage, "message": progress_info})

	def end_stage(self):
		if self.current_stage and self.stage_start_time:
			stage_duration = time.time() - self.stage_start_time
			stage_name = self.current_stage
			self.stage_times[stage_name] = stage_duration
			self.completed_stages += 1
			self._emit("stage_end", {"stage": stage_name, "duration": stage_duration, "completed": self.completed_stages, "total": self.total_stages})
			self.current_stage = None
			self.stage_start_time = None

	def end_workflow(self):
		if self.stage_start_time:
			self.end_stage()
		total_duration = time.time() - (self.start_time or time.time())
		self._emit("workflow_end", {"total_duration": total_duration, "stages": self.stage_times})
		return {"total_duration": total_duration, "stage_times": self.stage_times, "start_time": self.start_time, "end_time": time.time()}

	def set_event_callback(self, cb: Optional[Callable[[str, Dict[str, Any]], None]]) -> None:
		self.event_callback = cb

	def _emit(self, event: str, data: Dict[str, Any]) -> None:
		cb = self.event_callback
		if cb is None:
			return
		try:
			cb(event, data)
		except Exception:
			logger.debug("progress event callback error", exc_info=True)


progress_manager = ProgressManager()

