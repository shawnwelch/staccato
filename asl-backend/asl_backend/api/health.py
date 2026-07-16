from __future__ import annotations

from fastapi import APIRouter

from asl_backend.engine import ENGINE_VERSION

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "engine_version": ENGINE_VERSION}
