"""Exceptions for the webhook module."""


class WebhookSignatureError(Exception):
    """Raised when webhook HMAC-SHA256 signature verification fails."""
