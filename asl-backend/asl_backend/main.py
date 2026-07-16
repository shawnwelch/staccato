from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from asl_backend.config import get_settings
from asl_backend.db import get_engine
from asl_backend.jobs import app as procrastinate_app
from asl_backend.models import Base


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.env != "prod":
            # Dev/test convenience; production schema is managed by migrations.
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        async with procrastinate_app.open_async():
            yield

    app = FastAPI(
        title="ASL backend",
        version="0.1.0",
        description="Pacing scorer API — a neutral instrument for video pacing.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # public read endpoints are the growth surface
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from asl_backend.api import admin, analyses, apple, health, live_sessions, public

    app.include_router(health.router)
    app.include_router(analyses.router)
    app.include_router(live_sessions.router)
    app.include_router(public.router)
    app.include_router(apple.router)
    app.include_router(admin.router)

    if settings.storage_backend == "local":
        Path(settings.media_root).mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

    return app


app = create_app()
