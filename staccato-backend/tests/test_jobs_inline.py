"""End-to-end pipeline test: POST /v1/analyses → run the Procrastinate job
inline (InMemoryConnector) against a synthetic clip → poll shows a complete,
scored analysis with stored artifacts and a share slug."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("cv2")

import staccato_backend.db as db_module
import staccato_backend.jobs.tasks as tasks_module
from staccato_backend.jobs import app as procrastinate_app
from staccato_backend.models import Channel, ChannelScore
from staccato_backend.providers import ChannelVideoRef, NormalizedVideo, VideoMetadata
from tests.utils import write_synthetic_clip


class FakeProvider:
    """Serves a locally-generated clip instead of hitting YouTube."""

    name = "youtube"

    def __init__(self, shot_length_s: float = 2.0, duration_s: float = 40.0):
        self.shot_length_s = shot_length_s
        self.duration_s = duration_s

    def fetch_metadata(self, video: NormalizedVideo) -> VideoMetadata:
        return VideoMetadata(
            title=f"Synthetic {video.provider_video_id}",
            channel_provider_id="UC" + "x" * 22,
            channel_title="Synthetic Channel",
            duration_s=self.duration_s,
            view_count=1000,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def download_lowres(self, video: NormalizedVideo, dest_dir: Path) -> Path:
        path = dest_dir / f"{video.provider_video_id}.mp4"
        write_synthetic_clip(path, self.shot_length_s, self.duration_s)
        return path

    def normalize_channel_url(self, url: str) -> str | None:
        return "UC" + "x" * 22

    def list_recent_videos(self, provider_channel_id: str, n: int) -> list[ChannelVideoRef]:
        return [
            ChannelVideoRef(
                provider_video_id=f"synthvid{i:03d}",
                canonical_url=f"https://www.youtube.com/watch?v=synthvid{i:03d}",
                title=f"Synthetic video {i}",
                view_count=1000 * (i + 1),
                published_at=datetime(2026, 1, 1 + i, tzinfo=UTC),
            )
            for i in range(n)
        ]


async def _run_queued_jobs():
    await procrastinate_app.run_worker_async(
        wait=False, install_signal_handlers=False, listen_notify=False
    )


@pytest.mark.slow
async def test_url_analysis_pipeline(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr(tasks_module, "get_provider", lambda name: FakeProvider())

    created = await client.post(
        "/v1/analyses", json={"url": "https://youtu.be/pipelinevid"}, headers=auth_headers
    )
    assert created.status_code == 202
    analysis_id = created.json()["analysis"]["id"]

    await _run_queued_jobs()

    resp = await client.get(f"/v1/analyses/{analysis_id}", headers=auth_headers)
    body = resp.json()
    assert body["analysis"]["status"] == "complete", body
    assert 85 <= body["analysis"]["score"] <= 95  # 2s cuts ≈ 90
    assert body["analysis"]["label"] == "hyper-paced"
    assert body["analysis"]["heatmap_png_url"]
    assert body["analysis"]["result_json_url"]
    assert body["share_slug"]
    assert body["video"]["title"] == "Synthetic pipelinevid"

    # Public surfaces now serve it: share page + video lookup.
    share = await client.get(f"/v1/share/{body['share_slug']}")
    assert share.status_code == 200
    assert share.json()["analysis"]["score"] == body["analysis"]["score"]

    lookup = await client.get("/v1/videos/youtube/pipelinevid")
    assert lookup.status_code == 200
    assert lookup.json()["analysis"]["status"] == "complete"

    # And a second request for the same URL dedupes instantly.
    again = await client.post(
        "/v1/analyses", json={"url": "https://www.youtube.com/watch?v=pipelinevid"},
        headers=auth_headers,
    )
    assert again.json()["deduped"] is True


@pytest.mark.slow
async def test_channel_classification_pipeline(client, admin_headers, monkeypatch):
    monkeypatch.setattr(tasks_module, "get_provider", lambda name: FakeProvider(duration_s=30.0))
    import staccato_backend.api.admin as admin_module

    monkeypatch.setattr(admin_module, "get_provider", lambda name: FakeProvider())
    # Collapse the finalizer's retry delay so the inline worker drains it.
    monkeypatch.setattr(tasks_module, "_FINALIZE_RETRY_DELAY_S", 0)

    resp = await client.post(
        "/admin/channels/classify",
        json={"channel_url": "https://www.youtube.com/channel/UC" + "x" * 22, "n_videos": 3},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    channel_id = resp.json()["channel_id"]

    # classify_channel → 3x analyze_url → finalize_channel_score (self-reschedules)
    for _ in range(6):
        await _run_queued_jobs()

    sessionmaker = db_module.get_sessionmaker()
    async with sessionmaker() as session:
        from sqlalchemy import select

        score_row = await session.scalar(
            select(ChannelScore).where(ChannelScore.channel_id == channel_id)
        )
        assert score_row is not None, "channel score never finalized"
        assert 85 <= score_row.score <= 95
        assert score_row.n_videos == 3
        assert score_row.trend.value == "stable"
        assert len(score_row.per_video_series_json) == 3

    # Public channel endpoint serves it.
    channel_resp = await client.get(f"/v1/channels/{channel_id}")
    assert channel_resp.status_code == 200
    assert channel_resp.json()["score"]["n_videos"] == 3

    leaderboard = await client.get("/v1/leaderboard")
    assert leaderboard.status_code == 200
    assert leaderboard.json()["total"] == 1
    assert leaderboard.json()["items"][0]["channel_id"] == channel_id
