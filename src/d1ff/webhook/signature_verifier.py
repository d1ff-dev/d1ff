"""HMAC-SHA256 webhook signature verification."""

import hashlib
import hmac

import structlog

logger = structlog.get_logger()


def verify_signature(
    payload_body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify the HMAC-SHA256 signature of a GitHub webhook payload.

    Args:
        payload_body: Raw request body bytes (must NOT be decoded to str first).
        signature_header: Value of the X-Hub-Signature-256 header, or None.
        secret: The webhook secret configured in the GitHub App.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature_header:
        logger.info("webhook_signature_check", signature_valid=False, reason="missing_header")
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    result = hmac.compare_digest(expected, signature_header)
    logger.info("webhook_signature_check", signature_valid=result)
    return result
