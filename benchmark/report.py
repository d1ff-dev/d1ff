"""Benchmark report: metric calculation and output formatter (Story 7.1, FR56, AC: #2, #3).

Pure functions — no d1ff pipeline imports.  All calculation logic is testable
in isolation with fixture data.

Metrics produced
----------------
precision    : true_positives / (true_positives + false_positives)
recall       : true_positives / (true_positives + false_negatives)
noise_ratio  : false_positives / total_findings
avg_latency  : arithmetic mean latency per review (ms)
p95_latency  : 95th-percentile latency (ms)
avg_cost_usd : arithmetic mean cost per review (USD)
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Matching logic (pure, testable without any d1ff imports)
# ---------------------------------------------------------------------------

LINE_PROXIMITY = 3  # ±N lines counts as a match


def _normalize_path(path: str) -> str:
    """Normalise separators to forward-slashes and strip leading './'."""
    normed = path.replace("\\", "/")
    while normed.startswith("./"):
        normed = normed[2:]
    return normed


def is_true_positive(finding: dict[str, Any], known_bug: dict[str, Any]) -> bool:
    """Return True if *finding* matches *known_bug*.

    Matching rules (per story Dev Notes):
    - file path must match after normalisation (exact match)
    - |finding.line - known_bug.line| <= LINE_PROXIMITY
    """
    return _normalize_path(finding.get("file", "")) == _normalize_path(
        known_bug.get("file", "")
    ) and abs(int(finding.get("line", -1)) - int(known_bug.get("line", -1))) <= LINE_PROXIMITY


def classify_findings(
    findings: list[dict[str, Any]],
    known_bugs: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Classify findings into TP / FP / FN counts.

    Each known_bug can be matched at most once (greedy, first-match wins).

    Returns:
        (true_positives, false_positives, false_negatives)
    """
    matched_bugs: set[int] = set()  # indices into known_bugs already matched
    true_positives = 0
    false_positives = 0

    for finding in findings:
        matched = False
        for idx, bug in enumerate(known_bugs):
            if idx not in matched_bugs and is_true_positive(finding, bug):
                true_positives += 1
                matched_bugs.add(idx)
                matched = True
                break
        if not matched:
            false_positives += 1

    false_negatives = len(known_bugs) - len(matched_bugs)
    return true_positives, false_positives, false_negatives


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def _safe_div(numerator: float, denominator: float) -> float:
    """Return numerator / denominator, or 0.0 if denominator is zero."""
    return numerator / denominator if denominator else 0.0


def _percentile(values: list[float], p: float) -> float:
    """Return the p-th percentile of *values* (0–100).  Returns 0.0 for empty input."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p / 100
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def calculate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate quality and performance metrics from raw per-PR results.

    Args:
        results: List of per-PR result dicts as written to raw_results.json.

    Returns:
        Dict with keys: precision, recall, noise_ratio, avg_latency_ms,
        p95_latency_ms, avg_cost_usd.
    """
    total_tp = 0
    total_fp = 0
    total_fn = 0
    latencies: list[float] = []
    costs: list[float] = []

    for result in results:
        if result.get("status") != "ok":
            continue  # skip failed entries — don't skew averages

        findings: list[dict] = result.get("findings", [])
        known_bugs: list[dict] = result.get("known_bugs", [])

        tp, fp, fn = classify_findings(findings, known_bugs)
        total_tp += tp
        total_fp += fp
        total_fn += fn
        latencies.append(float(result.get("latency_ms", 0)))
        costs.append(float(result.get("cost_usd", 0.0)))

    precision = _safe_div(total_tp, total_tp + total_fp)
    recall = _safe_div(total_tp, total_tp + total_fn)
    total_findings = total_tp + total_fp
    noise_ratio = _safe_div(total_fp, total_findings)

    avg_latency = _safe_div(sum(latencies), len(latencies)) if latencies else 0.0
    p95_latency = _percentile(latencies, 95)
    avg_cost = _safe_div(sum(costs), len(costs)) if costs else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "noise_ratio": round(noise_ratio, 4),
        "avg_latency_ms": round(avg_latency),
        "p95_latency_ms": round(p95_latency),
        "avg_cost_usd": round(avg_cost, 6),
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _metrics_to_markdown(
    run_id: str,
    provider: str,
    model: str,
    dataset_size: int,
    metrics: dict[str, Any],
) -> str:
    """Render metrics as a human-readable markdown table."""
    precision_pct = f"{metrics['precision'] * 100:.1f}%"
    recall_pct = f"{metrics['recall'] * 100:.1f}%"
    noise_pct = f"{metrics['noise_ratio'] * 100:.1f}%"
    avg_lat = f"{metrics['avg_latency_ms'] / 1000:.1f}s"
    p95_lat = f"{metrics['p95_latency_ms'] / 1000:.1f}s"
    cost = f"${metrics['avg_cost_usd']:.4f}"

    return (
        f"## d1ff Benchmark Results — {run_id}\n\n"
        f"**Provider:** {provider} / **Model:** {model} / **Dataset:** {dataset_size} PRs\n\n"
        "| Metric          | Value   |\n"
        "|-----------------|--------|\n"
        f"| Precision       | {precision_pct:<7}|\n"
        f"| Recall          | {recall_pct:<7}|\n"
        f"| Noise Ratio     | {noise_pct:<7}|\n"
        f"| Avg Latency     | {avg_lat:<7}|\n"
        f"| P95 Latency     | {p95_lat:<7}|\n"
        f"| Avg Cost/Review | {cost:<7}|\n"
    )


def generate_report(raw_output: dict[str, Any]) -> dict[str, Any]:
    """Generate JSON and markdown reports from raw benchmark output.

    Args:
        raw_output: The full dict written to raw_results.json, containing keys:
                    run_id, provider, model, dataset_size, results.

    Returns:
        Dict with keys:
          "json"     → dict suitable for json.dumps (report.json content)
          "markdown" → str (report.md content)
    """
    run_id: str = raw_output["run_id"]
    provider: str = raw_output["provider"]
    model: str = raw_output["model"]
    dataset_size: int = raw_output["dataset_size"]
    results: list[dict] = raw_output["results"]

    metrics = calculate_metrics(results)

    report_json: dict[str, Any] = {
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "dataset_size": dataset_size,
        "metrics": metrics,
        "per_pr_results": results,
    }

    report_md = _metrics_to_markdown(run_id, provider, model, dataset_size, metrics)

    return {"json": report_json, "markdown": report_md}
