#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompts API - YAML-based prompt management endpoints.
Provides CRUD operations for prompts and bindings with Git versioning.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

from ...services.prompt_service import prompt_service
from ...services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["prompts"])


# Pydantic models for API
class PromptMetadata(BaseModel):
    """Prompt metadata for listing."""
    id: str
    path: str
    agent: Optional[str] = None
    workflow: Optional[str] = None
    locale: str
    version: int
    last_modified: float


class PromptContent(BaseModel):
    """Full prompt content."""
    id: str
    agent: Optional[str] = None
    locale: str
    version: int
    messages: List[Dict[str, str]]
    meta: Dict[str, Any]


class PromptUpdateRequest(BaseModel):
    """Request to update a prompt."""
    id: str
    agent: Optional[str] = None
    locale: str = "zh"
    version: int = Field(ge=1)
    messages: List[Dict[str, str]]
    meta: Dict[str, Any] = Field(default_factory=dict)


class PromptValidationRequest(BaseModel):
    """Request to validate prompt rendering."""
    agent: str
    locale: str = "zh"
    variables: Dict[str, Any]


class PromptValidationResponse(BaseModel):
    """Response from prompt validation."""
    valid: bool
    messages: List[Dict[str, str]]
    meta: Dict[str, Any]
    binding: Dict[str, Any]
    errors: List[str]


class PromptBinding(BaseModel):
    """Prompt binding configuration."""
    target_type: str
    target_id: str
    locale: str
    prompt_file: str
    model_ref: str
    params: Dict[str, Any] = Field(default_factory=dict)


class PromptBindingsUpdate(BaseModel):
    """Request to update prompt bindings."""
    bindings: List[PromptBinding]


class GitCommit(BaseModel):
    """Git commit information."""
    hash: str
    message: str
    short_hash: str


@router.get("/", response_model=List[PromptMetadata])
async def list_prompts():
    """
    List all available prompts with metadata.
    
    Returns:
        List of prompt metadata objects
    """
    try:
        prompts = prompt_service.list_prompts()
        return [PromptMetadata(**prompt) for prompt in prompts]
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list prompts: {str(e)}")


@router.get("/{path:path}", response_model=PromptContent)
async def get_prompt(path: str):
    """
    Get prompt content by file path.
    
    Args:
        path: Relative path to the prompt file (e.g., "agents/planner.zh.yaml")
        
    Returns:
        Full prompt content
    """
    try:
        # Load YAML content
        prompt_data = prompt_service._load_yaml(path)
        
        return PromptContent(
            id=prompt_data.get("id", ""),
            agent=prompt_data.get("agent"),
            locale=prompt_data.get("locale", "zh"),
            version=prompt_data.get("version", 1),
            messages=prompt_data.get("messages", []),
            meta=prompt_data.get("meta", {})
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {path}")
    except Exception as e:
        logger.error(f"Failed to get prompt {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get prompt: {str(e)}")


@router.put("/{path:path}")
async def update_prompt(
    path: str,
    prompt_data: PromptUpdateRequest,
    commit_message: str = Query(default="Update prompt", description="Git commit message")
):
    """
    Update prompt content and commit to Git.
    
    Args:
        path: Relative path to the prompt file
        prompt_data: New prompt content
        commit_message: Git commit message
        
    Returns:
        Success confirmation
    """
    try:
        # Convert to dict format expected by prompt_service
        yaml_data = {
            "id": prompt_data.id,
            "agent": prompt_data.agent,
            "locale": prompt_data.locale,
            "version": prompt_data.version,
            "messages": prompt_data.messages,
            "meta": prompt_data.meta
        }
        
        # Remove None values
        yaml_data = {k: v for k, v in yaml_data.items() if v is not None}
        
        # Save with Git commit
        success = prompt_service.save_prompt(path, yaml_data, commit_message)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to save prompt")
        
        return {"success": True, "message": "Prompt updated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to update prompt {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update prompt: {str(e)}")


@router.post("/validate", response_model=PromptValidationResponse)
async def validate_prompt(request: PromptValidationRequest):
    """
    Validate prompt rendering with variables.
    
    Args:
        request: Validation request with agent, locale, and variables
        
    Returns:
        Validation results including rendered messages
    """
    try:
        result = llm_service.validate_template(
            agent_name=request.agent,
            variables=request.variables,
            locale=request.locale
        )
        
        return PromptValidationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to validate prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate prompt: {str(e)}")


@router.get("/bindings/")
async def get_prompt_bindings():
    """
    Get current prompt bindings configuration.
    
    Returns:
        Current bindings configuration
    """
    try:
        bindings_data = prompt_service._load_yaml("prompt_bindings.yaml")
        return bindings_data
        
    except Exception as e:
        logger.error(f"Failed to get bindings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get bindings: {str(e)}")


@router.put("/bindings/")
async def update_prompt_bindings(
    bindings_update: PromptBindingsUpdate,
    commit_message: str = Query(default="Update prompt bindings", description="Git commit message")
):
    """
    Update prompt bindings configuration.
    
    Args:
        bindings_update: New bindings configuration
        commit_message: Git commit message
        
    Returns:
        Success confirmation
    """
    try:
        # Convert to dict format
        bindings_data = {
            "bindings": [binding.dict() for binding in bindings_update.bindings]
        }
        
        # Save bindings
        success = prompt_service.save_prompt("prompt_bindings.yaml", bindings_data, commit_message)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to save bindings")
        
        # Clear bindings cache
        prompt_service.bindings_cache = None
        
        return {"success": True, "message": "Bindings updated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to update bindings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update bindings: {str(e)}")


@router.get("/history/{path:path}", response_model=List[GitCommit])
async def get_prompt_history(
    path: str,
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of commits")
):
    """
    Get Git history for a prompt file.
    
    Args:
        path: Relative path to the prompt file
        limit: Maximum number of commits to return
        
    Returns:
        List of Git commit information
    """
    try:
        history = prompt_service.get_git_history(path, limit)
        return [GitCommit(**commit) for commit in history]
        
    except Exception as e:
        logger.error(f"Failed to get history for {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.post("/rollback/")
async def rollback_prompt(
    path: str = Body(..., description="Relative path to the prompt file"),
    commit_hash: str = Body(..., description="Git commit hash to rollback to"),
    confirm: bool = Body(False, description="Confirmation flag for rollback operation")
):
    """
    Rollback prompt to a specific Git commit.
    
    Args:
        path: Relative path to the prompt file
        commit_hash: Git commit hash to rollback to
        confirm: Confirmation flag (must be True)
        
    Returns:
        Success confirmation
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Rollback requires explicit confirmation. Set 'confirm' to true."
        )
    
    try:
        # This is a placeholder - actual Git rollback implementation would go here
        # For safety, this should be implemented with proper Git operations
        logger.warning(f"Rollback requested for {path} to {commit_hash} (not implemented)")
        
        raise HTTPException(
            status_code=501, 
            detail="Rollback functionality not yet implemented. Use Git CLI for now."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rollback {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


@router.post("/clear-cache/")
async def clear_prompt_cache():
    """
    Clear all prompt caches.
    
    Returns:
        Success confirmation
    """
    try:
        prompt_service.clear_cache()
        return {"success": True, "message": "Cache cleared successfully"}
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/agent/{agent_name}/info")
async def get_agent_info(agent_name: str, locale: str = Query(default="zh")):
    """
    Get information about an agent and its configuration.
    
    Args:
        agent_name: Name of the agent
        locale: Language locale
        
    Returns:
        Agent information including prompt binding details
    """
    try:
        info = llm_service.get_agent_info(agent_name, locale)
        return info
        
    except Exception as e:
        logger.error(f"Failed to get agent info for {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent info: {str(e)}")