from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="STACCATO_", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"

    # Neon Postgres. SQLAlchemy async URL (postgresql+asyncpg://...). In dev/test
    # an sqlite+aiosqlite URL also works for the API layer.
    database_url: str = "sqlite+aiosqlite:///./staccato_dev.sqlite3"
    # Plain psycopg URL for Procrastinate (it manages its own schema/pool).
    procrastinate_database_url: str = ""

    # Auth. "clerk" verifies RS256 JWTs against the JWKS; "dev" accepts
    # "Bearer dev:<user-id>" so local surfaces work without a Clerk tenant.
    auth_mode: Literal["clerk", "dev"] = "dev"
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    # Static bearer token for /admin (Clerk org-gating happens in staccato-admin;
    # this token authenticates the admin app's server-side proxy to us).
    admin_api_token: str = "dev-admin-token"

    # Object storage: Cloudflare R2 (S3-compatible) — decided per spec note.
    # "local" writes under media_root and serves via /media (dev only).
    storage_backend: Literal["r2", "local"] = "local"
    media_root: str = "./media"
    public_media_base_url: str = "http://localhost:8000/media"
    r2_endpoint_url: str = ""
    r2_bucket: str = "staccato-artifacts"
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""

    free_analyses_limit: int = 3
    share_base_url: str = "http://localhost:3000"

    # Channel classification / batch queue throttling
    channel_scan_default_n: int = 20
    batch_queue_throttle_s: float = 0.0  # sleep between batch fetches; raise on 429 storms
    youtube_api_key: str = ""

    apple_verify_signatures: bool = True
    # Directory of pinned Apple root CA certs (PEM or DER) for App Store
    # Server Notification chain validation; download from
    # https://www.apple.com/certificateauthority/. Verification fails closed
    # (503) if enabled without roots configured.
    apple_root_ca_dir: str = ""
    apple_bundle_id: str = "com.anythingsimple.staccato"

    yt_dlp_format: str = "worst[height>=240][ext=mp4]/worst[ext=mp4]/worst"


@lru_cache
def get_settings() -> Settings:
    return Settings()
