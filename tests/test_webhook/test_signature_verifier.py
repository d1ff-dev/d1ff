"""Tests for HMAC-SHA256 webhook signature verification."""

import hashlib
import hmac

from d1ff.webhook.signature_verifier import verify_signature

SECRET = "test-webhook-secret"
PAYLOAD = b'{"action": "created"}'


def _make_signature(payload: bytes, secret: str) -> str:
    """Helper to compute the expected HMAC signature string."""
    digest = hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def test_valid_signature_returns_true() -> None:
    sig = _make_signature(PAYLOAD, SECRET)
    assert verify_signature(PAYLOAD, sig, SECRET) is True


def test_invalid_signature_returns_false() -> None:
    assert verify_signature(PAYLOAD, "sha256=deadbeef", SECRET) is False


def test_missing_signature_returns_false() -> None:
    assert verify_signature(PAYLOAD, None, SECRET) is False


def test_empty_signature_returns_false() -> None:
    assert verify_signature(PAYLOAD, "", SECRET) is False


def test_signature_uses_compare_digest() -> None:
    """Ensure the implementation does not use plain string == for comparison.

    We inspect the source code of the verifier to confirm hmac.compare_digest
    is used rather than a naive equality check, which would be vulnerable to
    timing attacks (NFR9).
    """
    import inspect

    import d1ff.webhook.signature_verifier as module

    source = inspect.getsource(module)
    # Must use compare_digest
    assert "compare_digest" in source
    # Must NOT use plain == between the two signature strings
    # (we allow == only in type comparisons, e.g., `if not signature_header`)
    # We look for the pattern `expected == ` or `== signature_header` as a proxy
    assert "expected ==" not in source
    assert "== signature_header" not in source
