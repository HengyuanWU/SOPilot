from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

from .core.logging import setup_logging
from .core.lifecycle import register_lifecycle
from .api.v1.router import api_router
from .core.settings import settings_diagnostics


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="SOPilot API", version="0.1.0")
    # CORS（最小允许，本地开发）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    register_lifecycle(app)
    # 启动日志诊断（简要）
    try:
        diag = settings_diagnostics()
        import logging as _logging
        _logging.getLogger(__name__).info(f"settings: {diag}")
    except Exception:
        pass

    # 前端静态资源托管（容器构建产物位于 /app/frontend_dist）
    frontend_dir = os.getenv("FRONTEND_DIST_DIR", "/app/frontend_dist")
    index_file = os.path.join(frontend_dir, "index.html")
    assets_dir = os.path.join(frontend_dir, "assets")

    if os.path.exists(index_file):
        # 挂载静态资源（/assets/**）
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # 根路径返回前端首页
        @app.get("/")
        async def _serve_index():  # pragma: no cover
            return FileResponse(index_file)

        # SPA 路由回退：非 /api 与 /assets 的路径都交给前端
        @app.get("/{full_path:path}")
        async def _serve_spa(full_path: str):  # pragma: no cover
            # 不拦截API路径
            if full_path.startswith("api/"):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not Found")
            return FileResponse(index_file)
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.asgi:app", host="0.0.0.0", port=8000, reload=True)

