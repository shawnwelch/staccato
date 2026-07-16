"""Object storage for heat map PNGs and result JSON blobs.

Cloudflare R2 (S3-compatible) in production — chosen per the spec's
"decide early" note; boto3 talks to it with a custom endpoint URL. A local
filesystem backend serves dev/test via the API's /media static mount.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from staccato_backend.config import get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Store bytes, return a public URL."""
        ...


class LocalStorage:
    def __init__(self, root: str, base_url: str) -> None:
        self.root = Path(root)
        self.base_url = base_url.rstrip("/")

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"{self.base_url}/{key}"


class R2Storage:
    def __init__(self) -> None:
        import boto3

        s = get_settings()
        self.bucket = s.r2_bucket
        self.base_url = s.public_media_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=s.r2_endpoint_url,
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        return f"{self.base_url}/{key}"


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = R2Storage() if s.storage_backend == "r2" else LocalStorage(
            s.media_root, s.public_media_base_url
        )
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
