#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流API端点
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

from ...domain.workflows.registry import list_workflows, get_workflow_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows")


@router.get("", response_model=List[Dict[str, Any]])
async def get_workflows():
    """
    获取所有可用工作流列表
    
    Returns:
        工作流元数据列表
    """
    try:
        workflows = list_workflows()
        return [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "version": wf.version,
                "tags": wf.tags or [],
                "input_schema": wf.input_schema,
                "ui_schema": wf.ui_schema
            }
            for wf in workflows
        ]
    except Exception as e:
        logger.error(f"Error listing workflows: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow_detail(workflow_id: str):
    """
    获取指定工作流的详细信息
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        工作流详细元数据
    """
    try:
        metadata = get_workflow_metadata(workflow_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
            
        return {
            "id": metadata.id,
            "name": metadata.name,
            "description": metadata.description,
            "version": metadata.version,
            "tags": metadata.tags or [],
            "input_schema": metadata.input_schema,
            "ui_schema": metadata.ui_schema
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow: {str(e)}")


@router.get("/{workflow_id}/schema", response_model=Dict[str, Any])
async def get_workflow_schema(workflow_id: str):
    """
    获取工作流的输入Schema（用于动态表单生成）
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        工作流输入Schema和UI Schema
    """
    try:
        metadata = get_workflow_metadata(workflow_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
            
        return {
            "input_schema": metadata.input_schema,
            "ui_schema": metadata.ui_schema
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow schema {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow schema: {str(e)}")