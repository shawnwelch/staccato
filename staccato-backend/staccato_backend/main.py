from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from staccato_backend.config import get_settings
from staccato_backend.db import get_engine
from staccato_backend.jobs import app as procrastinate_app
from staccato_backend.models import Base


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
        title="Staccato backend",
        version="0.1.0",
        description="Pacing scorer API — a neutral instrument for video pacing.",
        lifespan=lifespan,
    )
    # Public read endpoints are the growth surface, so dev defaults to "*";
    # prod sets STACCATO_CORS_ALLOW_ORIGINS to an explicit allowlist.
    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    from staccato_backend.api import admin, analyses, apple, health, live_sessions, public

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
