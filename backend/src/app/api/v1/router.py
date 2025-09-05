from fastapi import APIRouter

from .runs import router as runs_router
from .kg import router as kg_router
from .prompts import router as prompts_router
from .workflows import router as workflows_router
from .rag import router as rag_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(runs_router, tags=["runs"])
api_router.include_router(kg_router, tags=["kg"])
api_router.include_router(prompts_router, tags=["prompts"])
api_router.include_router(workflows_router, tags=["workflows"])
api_router.include_router(rag_router, tags=["rag"]) 

