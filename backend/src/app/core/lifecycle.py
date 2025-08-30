from fastapi import FastAPI


def register_lifecycle(app: FastAPI) -> None:
    @app.on_event("startup")
    async def on_startup() -> None:  # noqa: F811
        # 预留：连接 Neo4j / 校验配置
        return None

    @app.on_event("shutdown")
    async def on_shutdown() -> None:  # noqa: F811
        # 预留：关闭连接
        return None

