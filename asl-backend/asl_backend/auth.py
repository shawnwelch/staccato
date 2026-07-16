"""Clerk-backed auth. Every authenticated route verifies a Clerk JWT.

Dev mode (`ASL_AUTH_MODE=dev`) accepts "Bearer dev:<user-id>" so local
surfaces and tests run without a Clerk tenant.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from asl_backend.config import get_settings
from asl_backend.db import get_session
from asl_backend.models import User

_bearer = HTTPBearer(auto_error=False)

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_S = 3600.0


@dataclass(frozen=True)
class Identity:
    user_id: str


async def _get_jwks() -> dict:
    settings = get_settings()
    now = time.monotonic()
    if _jwks_cache["keys"] is None or now - _jwks_cache["fetched_at"] > _JWKS_TTL_S:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.clerk_jwks_url)
            resp.raise_for_status()
            _jwks_cache["keys"] = resp.json()
            _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


async def _verify_clerk_jwt(token: str) -> str:
    settings = get_settings()
    jwks = await _get_jwks()
    try:
        header = jwt.get_unverified_header(token)
        key = next(k for k in jwks["keys"] if k.get("kid") == header.get("kid"))
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        claims = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer or None,
            options={"verify_aud": False},
        )
    except (StopIteration, jwt.PyJWTError) as exc:
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
        user_id = token.removeprefix("dev:")
        if not user_id:
            raise HTTPException(status_code=401, detail="invalid dev token")
    else:
        user_id = await _verify_clerk_jwt(token)

    # Mirror the Clerk user locally on first sight.
    existing = await session.scalar(select(User).where(User.clerk_user_id == user_id))
    if existing is None:
        session.add(User(clerk_user_id=user_id))
        await session.commit()
    return Identity(user_id=user_id)


async def require_admin(request: Request) -> None:
    """Admin surface auth: static bearer token from the asl-admin proxy.

    Clerk org-gating happens in asl-admin itself; this token authenticates
    that app's server-side calls to us.
    """
    settings = get_settings()
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {settings.admin_api_token}":
        raise HTTPException(status_code=401, detail="admin token required")
