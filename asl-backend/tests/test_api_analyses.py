from __future__ import annotations

from sqlalchemy import select

import asl_backend.db as db_module
from asl_backend.engine import ENGINE_VERSION
from asl_backend.jobs import app as procrastinate_app
from asl_backend.models import Analysis, AnalysisStatus, SharePage, Video


async def test_create_analysis_queues_job(client, auth_headers):
    resp = await client.post(
        "/v1/analyses",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        headers=auth_headers,
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["analysis"]["status"] == "queued"
    assert body["analysis"]["engine_version"] == ENGINE_VERSION
    assert body["deduped"] is False
    assert body["entitlement"]["free_remaining"] == 2
    assert body["video"]["provider_video_id"] == "dQw4w9WgXcQ"

    jobs = list(procrastinate_app.connector.jobs.values())
    assert len(jobs) == 1
    assert jobs[0]["task_name"] == "analyze_url"
    assert jobs[0]["queue_name"] == "interactive"


async def test_url_variants_normalize_to_same_video(client, auth_headers):
    r1 = await client.post(
        "/v1/analyses", json={"url": "https://youtu.be/dQw4w9WgXcQ"}, headers=auth_headers
    )
    r2 = await client.post(
        "/v1/analyses",
        json={"url": "https://www.youtube.com/shorts/dQw4w9WgXcQ"},
        headers=auth_headers,
    )
    assert r1.status_code == 202 and r2.status_code == 202
    async with db_module.get_sessionmaker()() as session:
        videos = (await session.scalars(select(Video))).all()
    assert len(videos) == 1


async def test_bad_url_rejected_and_no_credit_burned(client, auth_headers):
    resp = await client.post(
        "/v1/analyses", json={"url": "https://example.com/not-a-video"}, headers=auth_headers
    )
    assert resp.status_code == 422
    resp = await client.post(
        "/v1/analyses",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        headers=auth_headers,
    )
    assert resp.json()["entitlement"]["free_remaining"] == 2


async def test_requires_auth(client):
    resp = await client.post("/v1/analyses", json={"url": "https://youtu.be/dQw4w9WgXcQ"})
    assert resp.status_code == 401


async def test_dedupe_returns_completed_without_burning_credit(client, auth_headers):
    # Seed a completed analysis for the video at the current engine version.
    async with db_module.get_sessionmaker()() as session:
        video = Video(provider="youtube", provider_video_id="dQw4w9WgXcQ", title="Seeded")
        session.add(video)
        await session.flush()
        analysis = Analysis(
            video_id=video.id,
            status=AnalysisStatus.complete,
            source="url",
            engine_version=ENGINE_VERSION,
            score=72.5,
            label="fast",
            median_shot_s=4.0,
            cuts_per_minute=12.0,
            cut_count=48,
            duration_s=240.0,
        )
        session.add(analysis)
        await session.flush()
        session.add(SharePage(slug="seedslug", analysis_id=analysis.id))
        await session.commit()

    resp = await client.post(
        "/v1/analyses", json={"url": "https://youtu.be/dQw4w9WgXcQ"}, headers=auth_headers
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["deduped"] is True
    assert body["analysis"]["status"] == "complete"
    assert body["analysis"]["score"] == 72.5
    assert body["share_slug"] == "seedslug"
    # No credit burned, no job enqueued.
    assert body["entitlement"]["free_remaining"] == 3
    assert len(procrastinate_app.connector.jobs) == 0


async def test_free_quota_enforced_server_side(client, auth_headers):
    urls = [
        "https://youtu.be/aaaaaaaaaaa",
        "https://youtu.be/bbbbbbbbbbb",
        "https://youtu.be/ccccccccccc",
    ]
    for i, url in enumerate(urls):
        resp = await client.post("/v1/analyses", json={"url": url}, headers=auth_headers)
        assert resp.status_code == 202
        assert resp.json()["entitlement"]["free_remaining"] == 2 - i

    resp = await client.post(
        "/v1/analyses", json={"url": "https://youtu.be/ddddddddddd"}, headers=auth_headers
    )
    assert resp.status_code == 402
    assert resp.json()["detail"]["code"] == "free_quota_exhausted"
    assert resp.headers["x-scans-remaining"] == "0"


async def test_quota_header_on_create(client, auth_headers):
    resp = await client.post(
        "/v1/analyses", json={"url": "https://youtu.be/hhhhhhhhhhh"}, headers=auth_headers
    )
    assert resp.headers["x-scans-remaining"] == "2"


async def test_get_analysis_status(client, auth_headers):
    created = await client.post(
        "/v1/analyses", json={"url": "https://youtu.be/eeeeeeeeeee"}, headers=auth_headers
    )
    analysis_id = created.json()["analysis"]["id"]
    resp = await client.get(f"/v1/analyses/{analysis_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["analysis"]["status"] == "queued"

    resp = await client.get("/v1/analyses/nope", headers=auth_headers)
    assert resp.status_code == 404
