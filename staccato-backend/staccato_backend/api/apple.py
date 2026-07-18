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
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from staccato_backend.config import get_settings
from staccato_backend.db import get_session
from staccato_backend.models import (
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

    When STACCATO_APPLE_VERIFY_SIGNATURES is true (production), the x5c certificate
    chain is validated to a pinned Apple root CA (STACCATO_APPLE_ROOT_CA_DIR) and
    the JWS signature is checked against the leaf, before trusting the
    payload. Dev/test skips verification for locally-forged fixtures.
    """
    settings = get_settings()
    try:
        header_b64, payload_b64, _sig = jws.split(".")
        if settings.apple_verify_signatures:
            _verify_x5c_chain(jws, header_b64, settings.apple_root_ca_dir)
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="malformed signed payload") from exc


@lru_cache(maxsize=4)
def _load_pinned_roots(root_ca_dir: str) -> frozenset[bytes]:
    """Pinned trust anchors as DER bytes (Apple Root CA G2/G3, downloaded from
    https://www.apple.com/certificateauthority/ and deployed read-only)."""
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding

    roots: set[bytes] = set()
    for path in sorted(Path(root_ca_dir).glob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        try:
            cert = x509.load_pem_x509_certificate(data)
        except ValueError:
            cert = x509.load_der_x509_certificate(data)
        roots.add(cert.public_bytes(Encoding.DER))
    return frozenset(roots)


def _verify_signed_by(cert, issuer) -> None:
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

    public_key = issuer.public_key()
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(
            cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm)
        )
    elif isinstance(public_key, rsa.RSAPublicKey):
        public_key.verify(
            cert.signature,
            cert.tbs_certificate_bytes,
            padding.PKCS1v15(),
            cert.signature_hash_algorithm,
        )
    else:
        raise ValueError("unsupported issuer key type")


def _verify_x5c_chain(jws: str, header_b64: str, root_ca_dir: str) -> None:
    """Validate the header's certificate chain to a pinned Apple root, then
    verify the JWS against the leaf.

    The x5c chain is attacker-supplied, so the leaf is only trusted after
    every link's signature verifies and the terminal certificate is
    byte-identical to a pinned root. Fails closed if no roots are configured.
    """
    import jwt as pyjwt
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding

    if not root_ca_dir:
        raise HTTPException(
            status_code=503,
            detail="apple notification verification is enabled but no root CAs are configured",
        )
    pinned = _load_pinned_roots(root_ca_dir)
    if not pinned:
        raise HTTPException(status_code=503, detail="apple root CA directory is empty")

    padded = header_b64 + "=" * (-len(header_b64) % 4)
    header = json.loads(base64.urlsafe_b64decode(padded))
    x5c = header.get("x5c") or []
    if not x5c:
        raise HTTPException(status_code=400, detail="missing certificate chain")
    try:
        chain = [x509.load_der_x509_certificate(base64.b64decode(c)) for c in x5c]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="malformed certificate chain") from exc

    now = datetime.now(UTC)
    for cert in chain:
        if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
            raise HTTPException(status_code=400, detail="certificate outside validity window")
    try:
        for cert, issuer in zip(chain, chain[1:]):
            _verify_signed_by(cert, issuer)
    except Exception as exc:  # noqa: BLE001 — any crypto failure is a rejection
        raise HTTPException(status_code=400, detail="certificate chain verification failed") from exc

    if chain[-1].public_bytes(Encoding.DER) not in pinned:
        raise HTTPException(status_code=400, detail="certificate chain does not terminate at a pinned root")

    try:
        pyjwt.decode(
            jws, key=chain[0].public_key(), algorithms=["ES256"], options={"verify_aud": False}
        )
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=400, detail="invalid payload signature") from exc


def _check_notification_scope(data: dict, transaction_info: dict) -> None:
    """Reject notifications that aren't for OUR app in OUR environment.

    Apple signs Server Notifications for every app with the same chain, so
    chain validation alone accepts a replayed (legitimately signed)
    notification from any other developer's app — whose appAccountToken that
    developer controls. Bundle-id and environment checks close that hole.
    Only enforced when signature verification is on (prod); dev fixtures stay
    minimal.
    """
    settings = get_settings()
    if not settings.apple_verify_signatures:
        return
    for source in (data, transaction_info):
        bundle_id = source.get("bundleId")
        if bundle_id is not None and bundle_id != settings.apple_bundle_id:
            raise HTTPException(status_code=400, detail="notification is for a different app")
        environment = source.get("environment")
        if settings.env == "prod" and environment is not None and environment != "Production":
            raise HTTPException(status_code=400, detail="sandbox notification rejected in prod")
    if data.get("bundleId") is None:
        raise HTTPException(status_code=400, detail="notification missing bundleId")


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

    _check_notification_scope(data, transaction_info)

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
