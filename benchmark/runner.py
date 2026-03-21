"""Batch mode benchmark runner for d1ff (Story 7.1, FR55).

Processes every dataset entry in --dataset-dir without requiring live GitHub
webhooks.  Calls the d1ff pipeline directly with a ReviewContext constructed
from local diff and file data.

Usage::

    python benchmark/runner.py \\
        --dataset-dir benchmark/dataset/ \\
        --provider openai \\
        --model gpt-4o \\
        --output benchmark/results/

Environment variables
---------------------
LLM_API_KEY   (or BENCHMARK_API_KEY)   API key sent to the LLM provider.
BENCHMARK_PROVIDER                      Default provider (overridden by --provider).
BENCHMARK_MODEL                         Default model (overridden by --model).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Bootstrap: set required env vars BEFORE any d1ff module is imported so that
# pydantic-settings / lru_cache picks them up on first access.
# ---------------------------------------------------------------------------
import os
import sys

# Ensure repo root is on sys.path so `import d1ff` works when the script is
# run from any working directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

# Generate a temporary Fernet key for encrypting the LLM API key in
# ProviderConfig.  We do NOT need a persistent key — the encrypted value is
# only used within this process.
from cryptography.fernet import Fernet  # noqa: E402 — must come before d1ff imports

_BENCHMARK_FERNET_KEY = Fernet.generate_key().decode()

# Populate the mandatory settings that AppSettings requires so that
# get_settings() succeeds even without a .env file.
os.environ.setdefault("GITHUB_APP_ID", "0")
os.environ.setdefault("GITHUB_PRIVATE_KEY", "benchmark-placeholder")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "benchmark-placeholder")
os.environ.setdefault("ENCRYPTION_KEY", _BENCHMARK_FERNET_KEY)
os.environ.setdefault("GITHUB_CLIENT_ID", "benchmark-placeholder")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "benchmark-placeholder")
os.environ.setdefault("SESSION_SECRET_KEY", "benchmark-placeholder")

# ---------------------------------------------------------------------------
# Standard library + third-party imports (after env bootstrap)
# ---------------------------------------------------------------------------
import asyncio  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import click  # noqa: E402
import structlog  # noqa: E402

from benchmark.context_loader import load_dataset_entry  # noqa: E402

# ---------------------------------------------------------------------------
# d1ff imports (after env bootstrap)
# ---------------------------------------------------------------------------
from d1ff.pipeline.orchestrator import run_pipeline  # noqa: E402
from d1ff.providers.models import ProviderConfig  # noqa: E402

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper: build ProviderConfig for benchmark mode
# ---------------------------------------------------------------------------


def _make_provider_config(provider: str, model: str, api_key: str) -> ProviderConfig:
    """Construct a ProviderConfig for the benchmark run.

    The API key is Fernet-encrypted with the process-local key so that the
    existing llm_client.decrypt_value() path works transparently.
    """
    from d1ff.config import get_settings  # noqa: PLC0415 — lazy to ensure env already set
    from d1ff.storage.encryption import encrypt_value  # noqa: PLC0415

    encrypted_key = encrypt_value(api_key, get_settings().ENCRYPTION_KEY)
    return ProviderConfig(
        installation_id=0,
        provider=provider,
        model=model,
        api_key_encrypted=encrypted_key,
    )


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


async def _run_single_entry(
    entry_dir: Path,
    config: ProviderConfig,
) -> dict:
    """Run the pipeline on a single dataset entry and return a raw result dict."""
    metadata, context = load_dataset_entry(entry_dir)
    pr_id: str = metadata.get("pr_id", entry_dir.name)

    logger.info(
        "benchmark_entry_start",
        installation_id="benchmark",
        pr_number=pr_id,
        stage="benchmark_run",
    )

    start_ms = time.monotonic()
    try:
        _summary, verified_findings, cost_badge = await run_pipeline(context, config)
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        findings_list = [
            {
                "file": f.file,
                "line": f.line,
                "severity": f.severity,
                "category": f.category,
                "confidence": f.confidence,
                "message": f.message,
            }
            for f in verified_findings.findings
        ]

        total_cost = cost_badge.estimated_cost_usd if cost_badge else 0.0
        total_tokens = cost_badge.total_tokens if cost_badge else 0
        prompt_tokens = cost_badge.prompt_tokens if cost_badge else 0
        completion_tokens = cost_badge.completion_tokens if cost_badge else 0

        result: dict = {
            "pr_id": pr_id,
            "status": "ok",
            "latency_ms": elapsed_ms,
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": total_cost,
            "findings": findings_list,
            "known_bugs": metadata.get("known_bugs", []),
            "was_degraded": verified_findings.was_degraded,
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)
        logger.error(
            "benchmark_entry_failed",
            installation_id="benchmark",
            pr_number=pr_id,
            stage="benchmark_run",
            error=str(exc),
            latency_ms=elapsed_ms,
        )
        result = {
            "pr_id": pr_id,
            "status": "error",
            "error": str(exc),
            "latency_ms": elapsed_ms,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "findings": [],
            "known_bugs": metadata.get("known_bugs", []),
            "was_degraded": False,
        }

    logger.info(
        "benchmark_entry_complete",
        installation_id="benchmark",
        pr_number=pr_id,
        stage="benchmark_run",
        latency_ms=result["latency_ms"],
        findings_count=len(result["findings"]),
    )
    return result


async def _run_benchmark(
    dataset_dir: Path,
    output_dir: Path,
    provider: str,
    model: str,
    api_key: str,
    dry_run: bool,
) -> None:
    """Discover all dataset entries and run the benchmark."""
    # Discover entries: subdirectories containing metadata.json
    entries = sorted(
        d for d in dataset_dir.iterdir()
        if d.is_dir() and (d / "metadata.json").exists()
    )

    if not entries:
        click.echo(f"No dataset entries found in {dataset_dir}", err=True)
        raise SystemExit(1)

    click.echo(f"Found {len(entries)} dataset entries.")

    if dry_run:
        click.echo("[dry-run] Entries that would be processed:")
        for entry in entries:
            click.echo(f"  - {entry.name}")
        return

    config = _make_provider_config(provider, model, api_key)

    # Create timestamped output directory
    run_id = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H-%M-%S")
    run_output_dir = output_dir / run_id
    run_output_dir.mkdir(parents=True, exist_ok=True)

    raw_results: list[dict] = []
    for entry_dir in entries:
        click.echo(f"Processing {entry_dir.name}...")
        result = await _run_single_entry(entry_dir, config)
        raw_results.append(result)

    # Write raw results before report generation
    raw_results_path = run_output_dir / "raw_results.json"
    raw_output = {
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "dataset_size": len(raw_results),
        "results": raw_results,
    }
    raw_results_path.write_text(json.dumps(raw_output, indent=2), encoding="utf-8")
    click.echo(f"Raw results written to {raw_results_path}")

    # Generate report
    from benchmark.report import generate_report  # noqa: PLC0415 — lazy import

    report = generate_report(raw_output)

    report_json_path = run_output_dir / "report.json"
    report_md_path = run_output_dir / "report.md"
    report_json_path.write_text(json.dumps(report["json"], indent=2), encoding="utf-8")
    report_md_path.write_text(report["markdown"], encoding="utf-8")

    click.echo(f"Report JSON:     {report_json_path}")
    click.echo(f"Report Markdown: {report_md_path}")
    click.echo()
    click.echo(report["markdown"])


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--dataset-dir",
    default="benchmark/dataset/",
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the benchmark dataset directory.",
)
@click.option(
    "--provider",
    default=lambda: os.environ.get("BENCHMARK_PROVIDER", "openai"),
    show_default="openai (or $BENCHMARK_PROVIDER)",
    help="LLM provider name (e.g. openai, anthropic).",
)
@click.option(
    "--model",
    default=lambda: os.environ.get("BENCHMARK_MODEL", "gpt-4o"),
    show_default="gpt-4o (or $BENCHMARK_MODEL)",
    help="LLM model name (e.g. gpt-4o, claude-opus-4-5).",
)
@click.option(
    "--output",
    "output_dir",
    default="benchmark/results/",
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for benchmark results.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="List dataset entries without running the pipeline.",
)
def main(
    dataset_dir: Path,
    provider: str,
    model: str,
    output_dir: Path,
    dry_run: bool,
) -> None:
    """Run d1ff against a curated benchmark dataset and report quality metrics.

    The benchmark runner processes each dataset entry in batch mode, calling
    the d1ff review pipeline directly without live GitHub webhooks (FR55).
    Results include precision, recall, noise ratio, latency, and cost (FR56).
    """
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("BENCHMARK_API_KEY", "")
    if not api_key and not dry_run:
        click.echo(
            "Error: LLM_API_KEY (or BENCHMARK_API_KEY) environment variable is required.",
            err=True,
        )
        raise SystemExit(1)

    if not dataset_dir.exists():
        click.echo(f"Error: dataset directory not found: {dataset_dir}", err=True)
        raise SystemExit(1)

    asyncio.run(
        _run_benchmark(
            dataset_dir=dataset_dir,
            output_dir=output_dir,
            provider=provider,
            model=model,
            api_key=api_key,
            dry_run=dry_run,
        )
    )


if __name__ == "__main__":
    main()
