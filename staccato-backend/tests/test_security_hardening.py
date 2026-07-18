"""Regression tests for the security-audit hardening.

Pins the fail-closed behaviors: dev tokens and the default admin token are
refused in prod, Apple notifications are scoped to our bundle id and
environment, and live-session inputs are bounded.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import staccato_backend.api.apple as apple_module
import staccato_backend.auth as auth_module
import staccato_backend.db as db_module
from staccato_backend.api.apple import _check_notification_scope
from staccato_backend.config import get_settings
from staccato_backend.models import (
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


def _prod_settings(monkeypatch, module, **overrides):
    settings = get_settings().model_copy(update={"env": "prod", **overrides})
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    return settings


async def test_dev_tokens_rejected_in_prod(monkeypatch, client, auth_headers):
    _prod_settings(monkeypatch, auth_module, auth_mode="dev")
    resp = await client.post(
        "/v1/analyses", json={"url": "https://youtu.be/dQw4w9WgXcQ"}, headers=auth_headers
    )
    assert resp.status_code == 401


async def test_default_admin_token_refused_in_prod(monkeypatch, client, admin_headers):
    _prod_settings(monkeypatch, auth_module, admin_api_token="dev-admin-token")
    resp = await client.get("/admin/live-sessions", headers=admin_headers)
    assert resp.status_code == 503


async def test_admin_token_still_works_in_dev(client, admin_headers):
    resp = await client.get("/admin/live-sessions", headers=admin_headers)
    assert resp.status_code == 200


def test_apple_scope_rejects_foreign_bundle(monkeypatch):
    _prod_settings(monkeypatch, apple_module, apple_verify_signatures=True)
    with pytest.raises(HTTPException) as exc:
        _check_notification_scope({"bundleId": "com.evil.other"}, {})
    assert exc.value.status_code == 400


def test_apple_scope_rejects_sandbox_in_prod(monkeypatch):
    _prod_settings(monkeypatch, apple_module, apple_verify_signatures=True)
    with pytest.raises(HTTPException) as exc:
        _check_notification_scope(
            {"bundleId": get_settings().apple_bundle_id, "environment": "Sandbox"}, {}
        )
    assert exc.value.status_code == 400


def test_apple_scope_requires_bundle_id_when_verifying(monkeypatch):
    _prod_settings(monkeypatch, apple_module, apple_verify_signatures=True)
    with pytest.raises(HTTPException):
        _check_notification_scope({}, {})


def test_apple_scope_accepts_our_bundle(monkeypatch):
    settings = _prod_settings(monkeypatch, apple_module, apple_verify_signatures=True)
    _check_notification_scope(
        {"bundleId": settings.apple_bundle_id, "environment": "Production"},
        {"bundleId": settings.apple_bundle_id, "environment": "Production"},
    )


def test_apple_scope_skipped_when_verification_disabled(monkeypatch):
    _prod_settings(monkeypatch, apple_module, apple_verify_signatures=False)
    _check_notification_scope({}, {})  # dev fixtures stay minimal


async def test_live_session_duration_bound(client):
    await _make_pro("pro_dos")
    headers = {"Authorization": "Bearer dev:pro_dos"}
    resp = await client.post(
        "/v1/live-sessions",
        json={"cut_times_s": [1.0], "duration_s": 1e12},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_live_session_rejects_non_finite_floats(client):
    await _make_pro("pro_nan")
    headers = {"Authorization": "Bearer dev:pro_nan"}
    resp = await client.post(
        "/v1/live-sessions",
        json={"cut_times_s": ["NaN"], "duration_s": 10.0},
        headers=headers,
    )
    assert resp.status_code == 422
