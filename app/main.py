"""FastAPI 装配。启动时：初始化日志 → 加载 providers → 初始化 DB → 启动 worker。"""
from contextlib import asynccontextmanager

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api import (  # noqa: E402
    routes_dlq,
    routes_health,
    routes_metrics,
    routes_notifications,
    routes_providers,
)
from app.core.config import get_settings  # noqa: E402
from app.core.db import init_db  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.core.providers import get_registry  # noqa: E402
from app.delivery.worker import get_worker  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):  # FastAPI 协议要求接受 app 参数，本函数不使用
    setup_logging()
    log = structlog.get_logger("main")

    # 启动期硬性校验：providers.yaml 加载失败、token_env 缺失 → 直接拒绝起来
    try:
        registry = get_registry()
        log.info("providers_loaded", providers=registry.names())
    except Exception:
        log.exception("providers_load_failed")
        raise

    init_db()
    worker = get_worker()
    await worker.start()
    try:
        yield
    finally:
        await worker.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="rc_caohongwei notification gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    application.include_router(routes_notifications.router)
    application.include_router(routes_dlq.router)
    application.include_router(routes_providers.router)
    application.include_router(routes_health.router)
    application.include_router(routes_metrics.router)
    return application


app = create_app()
