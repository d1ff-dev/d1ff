"""Tests for d1ff.observability.log_config."""

import structlog

from d1ff.observability.log_config import configure_logging


def test_configure_logging_sets_json_renderer() -> None:
    """Smoke test: configure_logging sets structlog to JSON mode without errors."""
    configure_logging("INFO")
    logger = structlog.get_logger()
    # Emit a test event — should not raise
    logger.info("test_event", stage="test")
    # Verify structlog is configured (processors chain is set)
    config = structlog.get_config()
    processor_names = [type(p).__name__ for p in config["processors"]]
    assert "JSONRenderer" in processor_names
