"""x5c chain validation for App Store Server Notifications.

Builds a throwaway PKI (root → intermediate → leaf), pins the root, and
verifies that: a properly-chained JWS is accepted; an attacker's self-signed
leaf is rejected; a chain to an unpinned root is rejected; and verification
fails closed when no roots are configured.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID

import staccato_backend.api.apple as apple_module
from staccato_backend.api.apple import _decode_jws_payload
from staccato_backend.config import get_settings


def _make_cert(subject_name: str, *, issuer_cert=None, issuer_key=None, ca: bool):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_name)])
    issuer = issuer_cert.subject if issuer_cert is not None else subject
    signing_key = issuer_key if issuer_key is not None else key
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .sign(signing_key, hashes.SHA256())
    )
    return cert, key


@pytest.fixture()
def pki(tmp_path):
    root_cert, root_key = _make_cert("Test Apple Root CA", ca=True)
    inter_cert, inter_key = _make_cert(
        "Test Intermediate", issuer_cert=root_cert, issuer_key=root_key, ca=True
    )
    leaf_cert, leaf_key = _make_cert(
        "Test Leaf", issuer_cert=inter_cert, issuer_key=inter_key, ca=False
    )
    root_dir = tmp_path / "roots"
    root_dir.mkdir()
    (root_dir / "root.der").write_bytes(root_cert.public_bytes(Encoding.DER))
    return {
        "root_dir": str(root_dir),
        "chain": [leaf_cert, inter_cert, root_cert],
        "leaf_key": leaf_key,
    }


def _sign_jws(payload: dict, key, chain) -> str:
    x5c = [base64.b64encode(c.public_bytes(Encoding.DER)).decode() for c in chain]
    return pyjwt.encode(payload, key, algorithm="ES256", headers={"x5c": x5c})


@pytest.fixture()
def verifying_settings(monkeypatch, pki):
    settings = get_settings().model_copy(
        update={"apple_verify_signatures": True, "apple_root_ca_dir": pki["root_dir"]}
    )
    monkeypatch.setattr(apple_module, "get_settings", lambda: settings)
    return settings


def test_valid_chain_accepted(pki, verifying_settings):
    jws = _sign_jws({"notificationType": "TEST"}, pki["leaf_key"], pki["chain"])
    assert _decode_jws_payload(jws)["notificationType"] == "TEST"


def test_attacker_self_signed_leaf_rejected(pki, verifying_settings):
    evil_cert, evil_key = _make_cert("Evil Leaf", ca=False)
    jws = _sign_jws({"notificationType": "SUBSCRIBED"}, evil_key, [evil_cert])
    with pytest.raises(Exception) as exc_info:
        _decode_jws_payload(jws)
    assert getattr(exc_info.value, "status_code", None) == 400


def test_chain_to_unpinned_root_rejected(pki, verifying_settings):
    other_root, other_root_key = _make_cert("Other Root", ca=True)
    other_leaf, other_leaf_key = _make_cert(
        "Other Leaf", issuer_cert=other_root, issuer_key=other_root_key, ca=False
    )
    jws = _sign_jws({"notificationType": "SUBSCRIBED"}, other_leaf_key, [other_leaf, other_root])
    with pytest.raises(Exception) as exc_info:
        _decode_jws_payload(jws)
    assert getattr(exc_info.value, "status_code", None) == 400


def test_tampered_payload_rejected(pki, verifying_settings):
    jws = _sign_jws({"notificationType": "TEST"}, pki["leaf_key"], pki["chain"])
    header, _payload, sig = jws.split(".")
    forged = base64.urlsafe_b64encode(
        json.dumps({"notificationType": "SUBSCRIBED"}).encode()
    ).decode().rstrip("=")
    with pytest.raises(Exception) as exc_info:
        _decode_jws_payload(f"{header}.{forged}.{sig}")
    assert getattr(exc_info.value, "status_code", None) == 400


def test_fails_closed_without_configured_roots(monkeypatch, pki):
    settings = get_settings().model_copy(
        update={"apple_verify_signatures": True, "apple_root_ca_dir": ""}
    )
    monkeypatch.setattr(apple_module, "get_settings", lambda: settings)
    jws = _sign_jws({"notificationType": "TEST"}, pki["leaf_key"], pki["chain"])
    with pytest.raises(Exception) as exc_info:
        _decode_jws_payload(jws)
    assert getattr(exc_info.value, "status_code", None) == 503
