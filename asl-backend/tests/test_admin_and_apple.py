from __future__ import annotations

import base64
import json

import asl_backend.db as db_module
from asl_backend.deps.entitlements import load_entitlement
from asl_backend.models import LiveSession, User


def _fake_jws(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJFUzI1NiJ9.{body}.c2ln"


async def test_admin_requires_token(client):
    resp = await client.get("/admin/live-sessions")
    assert resp.status_code == 401
    resp = await client.get(
        "/admin/live-sessions", headers={"Authorization": "Bearer wrong"}
    )
    assert resp.status_code == 401


async def test_moderation_promote_flow(client, admin_headers):
    async with db_module.get_sessionmaker()() as session:
        session.add(User(clerk_user_id="capturer"))
        await session.flush()
        session.add(
            LiveSession(
                id="ls1",
                user_id="capturer",
                content_label="Show X",
                device_summary_json={"cut_times_s": [2.0], "duration_s": 10.0},
                duration_s=10.0,
                cut_count=1,
                device_score=50.0,
                recomputed_score=61.0,
                label="fast",
                engine_version="1.0.0",
            )
        )
        await session.commit()

    listing = await client.get("/admin/live-sessions", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["promoted"] is False

    resp = await client.post("/admin/live-sessions/ls1/promote", headers=admin_headers)
    assert resp.status_code == 200

    # Reviewed rows drop out of the default (unreviewed) moderation queue.
    listing = await client.get("/admin/live-sessions", headers=admin_headers)
    assert listing.json()["total"] == 0
    listing = await client.get(
        "/admin/live-sessions?promoted=true&reviewed=true", headers=admin_headers
    )
    assert listing.json()["total"] == 1


async def test_apple_subscription_lifecycle(client):
    """SUBSCRIBED grants pro; EXPIRED takes it away. appAccountToken carries
    the Clerk user id (set by the iOS app at purchase time)."""
    transaction = _fake_jws(
        {
            "appAccountToken": "apple_user_1",
            "originalTransactionId": "orig-txn-1",
            "expiresDate": 4102444800000,  # 2100-01-01
        }
    )
    resp = await client.post(
        "/v1/apple/notifications",
        json={
            "signedPayload": _fake_jws(
                {"notificationType": "SUBSCRIBED", "data": {"signedTransactionInfo": transaction}}
            )
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["handled"] is True

    async with db_module.get_sessionmaker()() as session:
        ent = await load_entitlement(session, "apple_user_1")
        assert ent.plan == "pro"
        assert ent.source == "apple"

    resp = await client.post(
        "/v1/apple/notifications",
        json={
            "signedPayload": _fake_jws(
                {"notificationType": "EXPIRED", "data": {"signedTransactionInfo": transaction}}
            )
        },
    )
    assert resp.json()["handled"] is True
    async with db_module.get_sessionmaker()() as session:
        ent = await load_entitlement(session, "apple_user_1")
        assert ent.plan == "free"


async def test_apple_unknown_notification_ignored(client):
    resp = await client.post(
        "/v1/apple/notifications",
        json={"signedPayload": _fake_jws({"notificationType": "TEST", "data": {}})},
    )
    assert resp.status_code == 200
    assert resp.json()["handled"] is False


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["engine_version"] == "1.0.0"


async def test_share_404(client):
    resp = await client.get("/v1/share/nosuchslug")
    assert resp.status_code == 404
