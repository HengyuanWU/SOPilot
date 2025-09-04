import os
import zipfile
import tempfile
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from ...services.workflow_service import create_run, get_run, stream_run
from ...domain.schemas.run import RunCreate, RunCreated, RunStatus
from ...infrastructure.storage.output_writer import list_run_artifacts, get_run_artifacts_dir


router = APIRouter(prefix="/runs")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("", response_model=RunCreated)
async def post_run(payload: RunCreate):
    run = create_run(payload.model_dump())
    return RunCreated(id=run["id"], status=run["status"])


@router.get("/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str) -> RunStatus:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return RunStatus(
        id=run["id"],
        status=run["status"],
        error=run.get("error"),
        result=run.get("result"),
        updated_at=run.get("updated_at"),
    )


@router.get("/{run_id}/stream")
async def stream_run_events(run_id: str):
    return StreamingResponse(stream_run(run_id), media_type="text/event-stream")


class ArtifactFile(BaseModel):
    name: str
    size: int
    modified: float
    type: str


@router.get("/{run_id}/artifacts", response_model=List[ArtifactFile])
async def get_run_artifacts(run_id: str) -> List[ArtifactFile]:
    """列出运行产物文件。"""
    try:
        artifacts = list_run_artifacts(run_id)
        return [ArtifactFile(**artifact) for artifact in artifacts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list artifacts: {str(e)}")


@router.get("/{run_id}/download")
async def download_run_file(run_id: str, file: str = Query(..., description="File name to download")):
    """下载单个运行产物文件。"""
    try:
        run_dir = get_run_artifacts_dir(run_id)
        file_path = os.path.join(run_dir, file)
        
        # 安全检查：确保文件在运行目录内
        if not os.path.commonpath([run_dir, file_path]) == run_dir:
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            path=file_path,
            filename=file,
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.get("/{run_id}/archive.zip")
async def download_run_archive(run_id: str):
    """打包下载所有运行产物。"""
    try:
        run_dir = get_run_artifacts_dir(run_id)
        
        if not os.path.exists(run_dir):
            raise HTTPException(status_code=404, detail="Run artifacts not found")
        
        # 创建临时ZIP文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_file.close()
        
        try:
            with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(run_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 使用相对路径作为ZIP内的路径
                        arcname = os.path.relpath(file_path, run_dir)
                        zipf.write(file_path, arcname)
            
            return FileResponse(
                path=temp_file.name,
                filename=f"run_{run_id}_artifacts.zip",
                media_type="application/zip",
                background=_cleanup_temp_file(temp_file.name)
            )
        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create archive: {str(e)}")


def _cleanup_temp_file(file_path: str):
    """后台任务：清理临时文件。"""
    def cleanup():
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass  # 忽略清理失败
    return cleanup

