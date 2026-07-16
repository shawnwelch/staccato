"""YouTube provider.

Frame access via yt-dlp at the lowest usable resolution (cut detection does
not need 1080p; ~360p is 5-10x faster to fetch and decode). Channel metadata
and view counts prefer the YouTube Data API when ASL_YOUTUBE_API_KEY is set —
that's the ToS-friendly path for metadata — falling back to yt-dlp extraction.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from asl_backend.config import get_settings
from asl_backend.providers import (
    ChannelVideoRef,
    NormalizedVideo,
    VideoMetadata,
)

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")


class YouTubeProvider:
    name = "youtube"

    # --- URL normalization (pure, unit-testable) ---

    def normalize_url(self, url: str) -> NormalizedVideo | None:
        url = url.strip()
        if not url:
            return None
        if _VIDEO_ID_RE.match(url):
            return self._normalized(url)
        if "//" not in url:
            url = "https://" + url
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        path = parsed.path or ""

        video_id: str | None = None
        if host == "youtu.be":
            video_id = path.strip("/").split("/")[0]
        elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
            if path == "/watch":
                video_id = (parse_qs(parsed.query).get("v") or [None])[0]
            else:
                m = re.match(r"^/(shorts|embed|live|v)/([A-Za-z0-9_-]{11})", path)
                if m:
                    video_id = m.group(2)
        if video_id and _VIDEO_ID_RE.match(video_id):
            return self._normalized(video_id)
        return None

    def _normalized(self, video_id: str) -> NormalizedVideo:
        return NormalizedVideo(
            provider=self.name,
            provider_video_id=video_id,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
        )

    def normalize_channel_url(self, url: str) -> str | None:
        url = url.strip()
        if _CHANNEL_ID_RE.match(url):
            return url
        if "//" not in url:
            url = "https://" + url
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        if host not in ("youtube.com",):
            return None
        path = (parsed.path or "").rstrip("/")
        m = re.match(r"^/channel/(UC[A-Za-z0-9_-]{22})$", path)
        if m:
            return m.group(1)
        # @handle and /c/name URLs need a lookup; return the path marker and
        # resolve at fetch time.
        m = re.match(r"^/(@[\w.\-]+)$", path)
        if m:
            return m.group(1)
        return None

    # --- Network paths (worker-only) ---

    def fetch_metadata(self, video: NormalizedVideo) -> VideoMetadata:
        info = self._ydl_extract(video.canonical_url, download=False)
        return VideoMetadata(
            title=info.get("title"),
            channel_provider_id=info.get("channel_id"),
            channel_title=info.get("channel") or info.get("uploader"),
            duration_s=float(info["duration"]) if info.get("duration") else None,
            view_count=info.get("view_count"),
            published_at=_parse_upload_date(info.get("upload_date")),
        )

    def download_lowres(self, video: NormalizedVideo, dest_dir: Path) -> Path:
        import yt_dlp

        settings = get_settings()
        dest_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(dest_dir / f"{video.provider_video_id}.%(ext)s")
        opts = {
            "format": settings.yt_dlp_format,
            "outtmpl": outtmpl,
            "quiet": True,
            "noprogress": True,
            "retries": 3,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video.canonical_url])
        files = list(dest_dir.glob(f"{video.provider_video_id}.*"))
        if not files:
            raise RuntimeError(f"yt-dlp produced no file for {video.canonical_url}")
        return files[0]

    def list_recent_videos(self, provider_channel_id: str, n: int) -> list[ChannelVideoRef]:
        settings = get_settings()
        if settings.youtube_api_key and provider_channel_id.startswith("UC"):
            try:
                return self._list_via_data_api(provider_channel_id, n)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # Back off hard on 429s per YouTube ToS expectations.
                    time.sleep(30)
                # fall through to yt-dlp
        return self._list_via_ytdlp(provider_channel_id, n)

    def _list_via_data_api(self, channel_id: str, n: int) -> list[ChannelVideoRef]:
        settings = get_settings()
        base = "https://www.googleapis.com/youtube/v3"
        with httpx.Client(timeout=20.0) as client:
            uploads = f"UU{channel_id[2:]}"  # uploads playlist id
            items: list[dict] = []
            page_token = ""
            while len(items) < n:
                resp = client.get(
                    f"{base}/playlistItems",
                    params={
                        "part": "contentDetails,snippet",
                        "playlistId": uploads,
                        "maxResults": min(50, n - len(items)),
                        "pageToken": page_token,
                        "key": settings.youtube_api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                items.extend(data.get("items", []))
                page_token = data.get("nextPageToken", "")
                if not page_token:
                    break
            video_ids = [i["contentDetails"]["videoId"] for i in items[:n]]
            stats: dict[str, int | None] = {}
            for chunk_start in range(0, len(video_ids), 50):
                chunk = video_ids[chunk_start : chunk_start + 50]
                resp = client.get(
                    f"{base}/videos",
                    params={
                        "part": "statistics",
                        "id": ",".join(chunk),
                        "key": settings.youtube_api_key,
                    },
                )
                resp.raise_for_status()
                for v in resp.json().get("items", []):
                    vc = v.get("statistics", {}).get("viewCount")
                    stats[v["id"]] = int(vc) if vc is not None else None
        refs = []
        for item in items[:n]:
            vid = item["contentDetails"]["videoId"]
            snippet = item.get("snippet", {})
            published = snippet.get("publishedAt")
            refs.append(
                ChannelVideoRef(
                    provider_video_id=vid,
                    canonical_url=f"https://www.youtube.com/watch?v={vid}",
                    title=snippet.get("title"),
                    view_count=stats.get(vid),
                    published_at=datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if published
                    else None,
                )
            )
        return refs

    def _list_via_ytdlp(self, channel_ref: str, n: int) -> list[ChannelVideoRef]:
        if channel_ref.startswith("UC"):
            url = f"https://www.youtube.com/channel/{channel_ref}/videos"
        else:
            url = f"https://www.youtube.com/{channel_ref}/videos"
        info = self._ydl_extract(url, download=False, extra={"playlistend": n, "extract_flat": True})
        refs = []
        for entry in (info.get("entries") or [])[:n]:
            vid = entry.get("id")
            if not vid:
                continue
            refs.append(
                ChannelVideoRef(
                    provider_video_id=vid,
                    canonical_url=f"https://www.youtube.com/watch?v={vid}",
                    title=entry.get("title"),
                    view_count=entry.get("view_count"),
                    published_at=None,
                )
            )
        return refs

    def _ydl_extract(self, url: str, download: bool, extra: dict | None = None) -> dict:
        import yt_dlp

        opts = {"quiet": True, "noprogress": True, "skip_download": not download}
        if extra:
            opts.update(extra)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)


def _parse_upload_date(upload_date: str | None) -> datetime | None:
    if not upload_date:
        return None
    try:
        return datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        return None
