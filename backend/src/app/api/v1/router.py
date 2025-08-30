from fastapi import APIRouter

from .runs import router as runs_router
from .kg import router as kg_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(runs_router, tags=["runs"])
api_router.include_router(kg_router, tags=["kg"]) 

