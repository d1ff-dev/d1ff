"""Pass 2 of the LLM pipeline: line-by-line PR review with structured output (FR13)."""

from __future__ import annotations

import json
import re
import time

import structlog
from pydantic import ValidationError

from d1ff.context.models import ReviewContext
from d1ff.pipeline.models import ReviewFinding, ReviewFindings
from d1ff.prompts import load_prompt
from d1ff.providers import call_llm_with_retry, get_provider_family
from d1ff.providers.models import ProviderConfig

logger = structlog.get_logger(__name__)


def _parse_findings_from_response(text: str) -> list[dict[str, object]]:
    """Strip markdown code fences and parse JSON list of findings."""
    stripped = re.sub(r"^```(?:json)?\n?", "", text.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"\n?```$", "", stripped.strip(), flags=re.MULTILINE)
    stripped = stripped.strip()
    result: list[dict[str, object]] = json.loads(stripped)
    return result


async def run_review_pass(context: ReviewContext, config: ProviderConfig) -> ReviewFindings:
    """Execute Pass 2: generate line-by-line review findings (FR13).

    Gracefully degrades: JSON parse failures return empty findings.
    Individual finding validation failures skip that finding.
    Exceptions from the LLM call propagate to the caller (orchestrator re-raises).
    """
    logger.info(
        "review_pass_start",
        installation_id=config.installation_id,
        stage="review_pass",
    )

    prompt = load_prompt(get_provider_family(config.provider, config.model), "review")

    file_contents = "\n\n".join(
        f"File: {fc.path}\n```\n{fc.content}\n```" for fc in context.changed_files
    )

    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                f"PR #{context.pr_metadata.number}: {context.pr_metadata.title}"
                f"\n\nDiff:\n{context.diff}"
                f"\n\nFile Contents:\n{file_contents}"
            ),
        },
    ]

    start_ms = time.monotonic()
    text, cost = await call_llm_with_retry(config, messages)
    elapsed_ms = int((time.monotonic() - start_ms) * 1000)

    validated_findings: list[ReviewFinding] = []

    try:
        raw_findings = _parse_findings_from_response(text)
        for raw in raw_findings:
            try:
                validated_findings.append(ReviewFinding.model_validate(raw))
            except ValidationError:
                logger.debug(
                    "review_finding_validation_skipped",
                    installation_id=config.installation_id,
                    stage="review_pass",
                )
    except json.JSONDecodeError:
        logger.warning(
            "review_pass_json_parse_failed",
            installation_id=config.installation_id,
            stage="review_pass",
        )

    logger.info(
        "review_pass_complete",
        installation_id=config.installation_id,
        stage="review_pass",
        duration_ms=elapsed_ms,
        findings_count=len(validated_findings),
    )

    return ReviewFindings(findings=validated_findings, cost=cost)
