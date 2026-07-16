from __future__ import annotations

from datetime import UTC, datetime, timedelta

import asl_backend.db as db_module
from asl_backend.models import (
    Entitlement,
    EntitlementPlan,
    EntitlementSource,
    EntitlementStatus,
    User,
)


async def _make_pro(user_id: str) -> None:
    async with db_module.get_sessionmaker()() as session:
        session.add(User(clerk_user_id=user_id))
        await session.flush()
        session.add(
            Entitlement(
                user_id=user_id,
                plan=EntitlementPlan.pro,
                source=EntitlementSource.apple,
                status=EntitlementStatus.active,
                current_period_end=datetime.now(UTC) + timedelta(days=30),
            )
        )
        await session.commit()


async def test_live_session_requires_pro(client, auth_headers):
    resp = await client.post(
        "/v1/live-sessions",
        json={"cut_times_s": [2.0, 4.0], "duration_s": 10.0},
        headers=auth_headers,
    )
    assert resp.status_code == 402
    assert resp.json()["detail"]["code"] == "pro_required"


async def test_live_session_recomputes_score_server_side(client):
    await _make_pro("pro_user")
    headers = {"Authorization": "Bearer dev:pro_user"}
    cut_times = [2.0 * i for i in range(1, 30)]  # 2s cadence over 60s
    resp = await client.post(
        "/v1/live-sessions",
        json={
            "cut_times_s": cut_times,
            "duration_s": 60.0,
            "device_score": 12.3,  # deliberately wrong client math
            "content_label": "Some Show S01E01",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert round(body["recomputed_score"], 1) == 90.2  # server math wins
    assert body["device_score"] == 12.3
    assert body["label"] == "hyper-paced"
    assert body["promoted"] is False  # optical scans start unmoderated


async def test_live_session_rejects_out_of_range_cuts(client):
    await _make_pro("pro_user2")
    headers = {"Authorization": "Bearer dev:pro_user2"}
    resp = await client.post(
        "/v1/live-sessions",
        json={"cut_times_s": [5.0, 99.0], "duration_s": 10.0},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_expired_subscription_is_not_pro(client):
    async with db_module.get_sessionmaker()() as session:
        session.add(User(clerk_user_id="lapsed"))
        await session.flush()
        session.add(
            Entitlement(
                user_id="lapsed",
                plan=EntitlementPlan.pro,
                source=EntitlementSource.apple,
                status=EntitlementStatus.active,
                current_period_end=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await session.commit()
    resp = await client.post(
        "/v1/live-sessions",
        json={"cut_times_s": [2.0], "duration_s": 10.0},
        headers={"Authorization": "Bearer dev:lapsed"},
    )
    assert resp.status_code == 402
