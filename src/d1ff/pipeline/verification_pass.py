"""Pass 3 of the LLM pipeline: verification and noise filtering (FR14, NFR21)."""

from __future__ import annotations

import json
import re
import time

import structlog
from pydantic import ValidationError

from d1ff.context.models import ReviewContext
from d1ff.pipeline.models import ReviewFinding, ReviewFindings, VerifiedFindings
from d1ff.prompts import load_prompt
from d1ff.providers import CostRecord, call_llm_with_retry, get_provider_family
from d1ff.providers.models import ProviderConfig

logger = structlog.get_logger(__name__)


def _parse_verified_findings_from_response(text: str) -> list[dict[str, object]]:
    """Strip markdown code fences and parse JSON list of findings."""
    stripped = re.sub(r"^```(?:json)?\n?", "", text.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"\n?```$", "", stripped.strip(), flags=re.MULTILINE)
    parsed = json.loads(stripped.strip())
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")
    result: list[dict[str, object]] = parsed
    return result


async def run_verification_pass(
    findings: ReviewFindings, context: ReviewContext, config: ProviderConfig
) -> VerifiedFindings:
    """Execute Pass 3: filter noise and duplicates from Pass 2 findings (FR14).

    Graceful degradation:
    - Empty findings → skip LLM call, return empty VerifiedFindings immediately.
    - JSON parse failure → return unverified findings with was_degraded=True (NFR21).
    - Individual finding validation failure → skip that finding (log DEBUG).
    - LLM call exceptions propagate to caller (orchestrator catches and falls back).
    """
    # Optimization: skip LLM call if no findings to verify
    if not findings.findings:
        return VerifiedFindings(
            findings=[],
            cost=CostRecord(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated_cost_usd=0.0,
                model=config.model,
            ),
            was_degraded=False,
        )

    logger.info(
        "verification_pass_start",
        installation_id=config.installation_id,
        stage="verification_pass",
        input_findings_count=len(findings.findings),
    )

    prompt = load_prompt(get_provider_family(config.provider, config.model), "verify")

    findings_json = json.dumps(
        [f.model_dump() for f in findings.findings],
        indent=2,
    )
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                f"PR Diff:\n{context.diff}\n\n"
                f"Review Findings to Verify:\n```json\n{findings_json}\n```"
            ),
        },
    ]

    start_ms = time.monotonic()
    text, cost = await call_llm_with_retry(config, messages)
    elapsed_ms = int((time.monotonic() - start_ms) * 1000)

    validated_findings: list[ReviewFinding] = []

    try:
        raw_findings = _parse_verified_findings_from_response(text)
        for raw in raw_findings:
            try:
                validated_findings.append(ReviewFinding.model_validate(raw))
            except ValidationError:
                logger.debug(
                    "verification_finding_validation_skipped",
                    installation_id=config.installation_id,
                    stage="verification_pass",
                )
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "verification_pass_json_parse_error",
            installation_id=config.installation_id,
            stage="verification_pass",
            error=str(exc),
        )
        return VerifiedFindings(
            findings=findings.findings,
            cost=cost,
            was_degraded=True,
        )

    output_keys = {(f.file, f.line, f.category, f.severity) for f in validated_findings}
    filtered = [
        f for f in findings.findings
        if (f.file, f.line, f.category, f.severity) not in output_keys
    ]

    logger.info(
        "verification_pass_complete",
        installation_id=config.installation_id,
        stage="verification_pass",
        duration_ms=elapsed_ms,
        input_count=len(findings.findings),
        output_count=len(validated_findings),
        filtered_count=len(filtered),
        filtered_categories=sorted({f.category for f in filtered}),
    )

    return VerifiedFindings(findings=validated_findings, cost=cost, was_degraded=False)
