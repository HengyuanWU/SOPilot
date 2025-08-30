from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ...services.workflow_service import create_run, get_run, stream_run
from ...domain.schemas.run import RunCreate, RunCreated, RunStatus


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

