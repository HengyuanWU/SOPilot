#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流注册中心 - 统一管理多工作流发现与元数据
"""

import logging
from importlib import import_module
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WorkflowMetadata:
    """工作流元数据结构"""
    id: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    ui_schema: Optional[Dict[str, Any]] = None
    version: str = "1.0.0"
    tags: List[str] = None


class WorkflowRegistry:
    """工作流注册中心 - 动态发现与管理工作流"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._metadata_cache: Dict[str, WorkflowMetadata] = {}
        self.base_path = Path(__file__).parent
        
    def list_workflows(self) -> List[WorkflowMetadata]:
        """
        枚举所有可用工作流
        
        Returns:
            工作流元数据列表
        """
        workflows = []
        
        # 扫描工作流目录
        for workflow_dir in self.base_path.iterdir():
            if (workflow_dir.is_dir() and 
                workflow_dir.name not in ['__pycache__', '.pytest_cache'] and
                (workflow_dir / 'graph.py').exists()):
                
                try:
                    metadata = self._get_workflow_metadata(workflow_dir.name)
                    if metadata:
                        workflows.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to load workflow {workflow_dir.name}: {e}")
                    
        return workflows
    
    def get_workflow(self, workflow_id: str):
        """
        获取工作流实例
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流实例
            
        Raises:
            ValueError: 工作流不存在
        """
        if workflow_id in self._cache:
            return self._cache[workflow_id]
            
        try:
            # 动态导入工作流模块
            module_path = f'app.domain.workflows.{workflow_id}.graph'
            module = import_module(module_path)
            
            # 获取工作流实例
            if hasattr(module, 'get_workflow'):
                workflow = module.get_workflow()
                self._cache[workflow_id] = workflow
                return workflow
            else:
                raise ValueError(f"Workflow {workflow_id} does not export get_workflow() function")
                
        except ImportError as e:
            raise ValueError(f"Workflow {workflow_id} not found: {e}")
            
    def get_workflow_metadata(self, workflow_id: str) -> Optional[WorkflowMetadata]:
        """
        获取工作流元数据
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流元数据，如果不存在返回None
        """
        return self._get_workflow_metadata(workflow_id)
    
    def _get_workflow_metadata(self, workflow_id: str) -> Optional[WorkflowMetadata]:
        """
        内部方法：获取工作流元数据
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流元数据
        """
        if workflow_id in self._metadata_cache:
            return self._metadata_cache[workflow_id]
            
        try:
            # 动态导入工作流模块
            module_path = f'app.domain.workflows.{workflow_id}.graph'
            module = import_module(module_path)
            
            # 获取元数据
            if hasattr(module, 'get_metadata'):
                metadata_dict = module.get_metadata()
                metadata = WorkflowMetadata(**metadata_dict)
                self._metadata_cache[workflow_id] = metadata
                return metadata
            else:
                # 如果没有get_metadata函数，提供默认元数据
                logger.warning(f"Workflow {workflow_id} does not export get_metadata() function, using defaults")
                metadata = WorkflowMetadata(
                    id=workflow_id,
                    name=workflow_id.title(),
                    description=f"工作流: {workflow_id}",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "title": "主题",
                                "description": "请输入主题"
                            }
                        },
                        "required": ["topic"]
                    }
                )
                self._metadata_cache[workflow_id] = metadata
                return metadata
                
        except ImportError as e:
            logger.error(f"Failed to import workflow {workflow_id}: {e}")
            return None
    
    def register_workflow(self, workflow_id: str, workflow_instance, metadata: WorkflowMetadata):
        """
        手动注册工作流（用于测试或动态注册）
        
        Args:
            workflow_id: 工作流ID
            workflow_instance: 工作流实例
            metadata: 工作流元数据
        """
        self._cache[workflow_id] = workflow_instance
        self._metadata_cache[workflow_id] = metadata
        
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._metadata_cache.clear()


# 全局单例
workflow_registry = WorkflowRegistry()


# 便捷函数
def list_workflows() -> List[WorkflowMetadata]:
    """枚举所有可用工作流"""
    return workflow_registry.list_workflows()


def get_workflow(workflow_id: str):
    """获取工作流实例"""
    return workflow_registry.get_workflow(workflow_id)


def get_workflow_metadata(workflow_id: str) -> Optional[WorkflowMetadata]:
    """获取工作流元数据"""
    return workflow_registry.get_workflow_metadata(workflow_id)