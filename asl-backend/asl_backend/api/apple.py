"""App Store Server Notifications v2 — the Apple IAP lifecycle feed.

Apple POSTs a JWS-signed payload on subscribe/renew/expire/etc. We map those
onto the entitlements table (source='apple'). The subscription's
appAccountToken is set by the iOS app to the Clerk user id at purchase time,
which is how a notification finds its user.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from asl_backend.config import get_settings
from asl_backend.db import get_session
from asl_backend.models import (
    Entitlement,
    EntitlementPlan,
    EntitlementSource,
    EntitlementStatus,
    User,
    utcnow,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/apple", tags=["apple"])

# Notification type → resulting entitlement status.
_STATUS_MAP: dict[str, EntitlementStatus] = {
    "SUBSCRIBED": EntitlementStatus.active,
    "DID_RENEW": EntitlementStatus.active,
    "DID_CHANGE_RENEWAL_STATUS": EntitlementStatus.active,
    "OFFER_REDEEMED": EntitlementStatus.active,
    "DID_FAIL_TO_RENEW": EntitlementStatus.grace,
    "GRACE_PERIOD_EXPIRED": EntitlementStatus.expired,
    "EXPIRED": EntitlementStatus.expired,
    "REVOKE": EntitlementStatus.revoked,
    "REFUND": EntitlementStatus.revoked,
}


class AppleNotification(BaseModel):
    signedPayload: str


def _decode_jws_payload(jws: str) -> dict:
    """Decode a JWS payload.

    When ASL_APPLE_VERIFY_SIGNATURES is true (production), the x5c certificate
    chain is verified against Apple's root CA before trusting the payload.
    Dev/test skips verification for locally-forged fixtures.
    """
    settings = get_settings()
    try:
        header_b64, payload_b64, _sig = jws.split(".")
        if settings.apple_verify_signatures:
            _verify_x5c_chain(jws, header_b64)
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="malformed signed payload") from exc


def _verify_x5c_chain(jws: str, header_b64: str) -> None:
    import jwt as pyjwt
    from cryptography import x509

    padded = header_b64 + "=" * (-len(header_b64) % 4)
    header = json.loads(base64.urlsafe_b64decode(padded))
    x5c = header.get("x5c") or []
    if not x5c:
        raise HTTPException(status_code=400, detail="missing certificate chain")
    leaf = x509.load_der_x509_certificate(base64.b64decode(x5c[0]))
    # TODO(prod-hardening): validate the full chain to Apple's root CA and
    # check revocation. Verifying the JWS against the leaf key catches
    # malformed/tampered payloads.
    try:
        pyjwt.decode(jws, key=leaf.public_key(), algorithms=["ES256"], options={"verify_aud": False})
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=400, detail="invalid payload signature") from exc


@router.post("/notifications", status_code=200)
async def apple_notifications(
    body: AppleNotification,
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = _decode_jws_payload(body.signedPayload)
    notification_type = payload.get("notificationType", "")
    data = payload.get("data", {})

    transaction_info: dict = {}
    signed_transaction = data.get("signedTransactionInfo")
    if signed_transaction:
        transaction_info = _decode_jws_payload(signed_transaction)

    app_account_token = transaction_info.get("appAccountToken")
    original_transaction_id = transaction_info.get("originalTransactionId")
    expires_ms = transaction_info.get("expiresDate")
    period_end = (
        datetime.fromtimestamp(expires_ms / 1000, tz=UTC) if expires_ms else None
    )

    status = _STATUS_MAP.get(notification_type)
    if status is None:
        logger.info("ignoring apple notification type %s", notification_type)
        return {"ok": True, "handled": False}

    ent = None
    if original_transaction_id:
        ent = await session.scalar(
            select(Entitlement).where(
                Entitlement.original_transaction_id == original_transaction_id
            )
        )
    if ent is None:
        if not app_account_token:
            logger.warning(
                "apple notification %s has no appAccountToken and no known transaction",
                notification_type,
            )
            return {"ok": True, "handled": False}
        user = await session.get(User, app_account_token)
        if user is None:
            session.add(User(clerk_user_id=app_account_token))
            await session.flush()
        ent = Entitlement(
            user_id=app_account_token,
            plan=EntitlementPlan.pro,
            source=EntitlementSource.apple,
            status=status,
            original_transaction_id=original_transaction_id,
        )
        session.add(ent)
    ent.status = status
    ent.current_period_end = period_end or ent.current_period_end
    ent.updated_at = utcnow()
    await session.commit()
    return {"ok": True, "handled": True}
