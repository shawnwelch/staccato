"""Clerk-backed auth. Every authenticated route verifies a Clerk JWT.

Dev mode (`STACCATO_AUTH_MODE=dev`) accepts "Bearer dev:<user-id>" so local
surfaces and tests run without a Clerk tenant. Dev tokens are never honored
when STACCATO_ENV=prod, regardless of auth_mode.
"""

from __future__ import annotations

import asyncio
import hmac
import time

from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from staccato_backend.config import get_settings
from staccato_backend.db import get_session
from staccato_backend.models import User

_bearer = HTTPBearer(auto_error=False)

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_jwks_lock = asyncio.Lock()
_JWKS_TTL_S = 3600.0
# Floor between forced refetches on an unknown kid, so a flood of garbage
# tokens can't turn the JWKS endpoint into an amplification target.
_JWKS_MIN_REFRESH_S = 60.0

# The dev-mode admin token; never accepted in prod (see require_admin).
_DEV_ADMIN_TOKEN = "dev-admin-token"


@dataclass(frozen=True)
class Identity:
    user_id: str


async def _fetch_jwks() -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(settings.clerk_jwks_url)
        resp.raise_for_status()
        return resp.json()


async def _get_jwks(force: bool = False) -> dict:
    now = time.monotonic()
    stale = _jwks_cache["keys"] is None or now - _jwks_cache["fetched_at"] > _JWKS_TTL_S
    refreshable = now - _jwks_cache["fetched_at"] > _JWKS_MIN_REFRESH_S
    if stale or (force and refreshable):
        # Single flight: concurrent cold-cache requests share one fetch
        # instead of stampeding the JWKS endpoint.
        async with _jwks_lock:
            now = time.monotonic()
            stale = _jwks_cache["keys"] is None or now - _jwks_cache["fetched_at"] > _JWKS_TTL_S
            refreshable = now - _jwks_cache["fetched_at"] > _JWKS_MIN_REFRESH_S
            if stale or (force and refreshable):
                _jwks_cache["keys"] = await _fetch_jwks()
                _jwks_cache["fetched_at"] = time.monotonic()
    return _jwks_cache["keys"]


def _find_key(jwks: dict, kid: str | None):
    return next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)


async def _verify_clerk_jwt(token: str) -> str:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    jwks = await _get_jwks()
    key = _find_key(jwks, header.get("kid"))
    if key is None:
        # Unknown kid: Clerk may have rotated its signing keys inside our TTL.
        # Refetch once (rate-limited) before rejecting.
        jwks = await _get_jwks(force=True)
        key = _find_key(jwks, header.get("kid"))
    if key is None:
        raise HTTPException(status_code=401, detail="invalid token")
    try:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        claims = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer or None,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="invalid token")
    return sub


async def require_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Identity:
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = credentials.credentials
    settings = get_settings()

    if settings.auth_mode == "dev" and token.startswith("dev:"):
        # Dev tokens are a local convenience only — a prod deploy that is
        # misconfigured to auth_mode=dev must not become an open API.
        if settings.env == "prod":
            raise HTTPException(status_code=401, detail="invalid token")
        user_id = token.removeprefix("dev:")
        if not user_id:
            raise HTTPException(status_code=401, detail="invalid dev token")
    else:
        user_id = await _verify_clerk_jwt(token)

    # Mirror the Clerk user locally on first sight. INSERT .. ON CONFLICT DO
    # NOTHING so two concurrent first-sight requests can't race into an
    # IntegrityError.
    existing = await session.scalar(select(User).where(User.clerk_user_id == user_id))
    if existing is None:
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        await session.execute(
            upsert(User)
            .values(clerk_user_id=user_id)
            .on_conflict_do_nothing(index_elements=["clerk_user_id"])
        )
        await session.commit()
    return Identity(user_id=user_id)


async def require_admin(request: Request) -> None:
    """Admin surface auth: static bearer token from the staccato-admin proxy.

    Clerk org-gating happens in staccato-admin itself; this token authenticates
    that app's server-side calls to us. Comparison is constant-time, and the
    well-known dev default token is refused outright in prod so a deploy that
    forgot to set STACCATO_ADMIN_API_TOKEN fails closed instead of open.
    """
    settings = get_settings()
    if settings.env == "prod" and settings.admin_api_token == _DEV_ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="admin token not configured")
    auth = request.headers.get("authorization", "")
    expected = f"Bearer {settings.admin_api_token}"
    if not hmac.compare_digest(auth.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="admin token required")
