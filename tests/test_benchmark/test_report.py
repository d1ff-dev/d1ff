"""Tests for benchmark/report.py (Story 7.1, AC: #2, #3).

Verifies precision/recall/noise calculations and output formatting using
fixture data.  No real LLM calls are made.
"""

from __future__ import annotations

import json

import pytest

from benchmark.report import (
    _percentile,
    _safe_div,
    calculate_metrics,
    classify_findings,
    generate_report,
    is_true_positive,
)

# ---------------------------------------------------------------------------
# Helpers / fixture data
# ---------------------------------------------------------------------------


def _finding(file: str, line: int) -> dict:
    return {
        "file": file,
        "line": line,
        "severity": "warning",
        "category": "bug",
        "confidence": "high",
        "message": "Test finding",
    }


def _bug(file: str, line: int) -> dict:
    return {"file": file, "line": line, "description": "Known bug", "severity": "high"}


def _result(
    findings: list[dict],
    known_bugs: list[dict],
    latency_ms: int = 1000,
    cost_usd: float = 0.01,
    status: str = "ok",
) -> dict:
    return {
        "pr_id": "pr-test",
        "status": status,
        "latency_ms": latency_ms,
        "total_tokens": 100,
        "prompt_tokens": 80,
        "completion_tokens": 20,
        "cost_usd": cost_usd,
        "findings": findings,
        "known_bugs": known_bugs,
        "was_degraded": False,
    }


# ---------------------------------------------------------------------------
# Tests: is_true_positive
# ---------------------------------------------------------------------------


def test_is_true_positive_exact_match() -> None:
    assert is_true_positive(_finding("src/api/users.py", 42), _bug("src/api/users.py", 42))


def test_is_true_positive_within_proximity_positive() -> None:
    assert is_true_positive(_finding("src/api/users.py", 42), _bug("src/api/users.py", 45))


def test_is_true_positive_at_proximity_boundary() -> None:
    assert is_true_positive(_finding("src/api/users.py", 42), _bug("src/api/users.py", 39))


def test_is_true_positive_outside_proximity() -> None:
    assert not is_true_positive(_finding("src/api/users.py", 42), _bug("src/api/users.py", 46))


def test_is_true_positive_wrong_file() -> None:
    # Same line, different file → no match
    assert not is_true_positive(_finding("src/api/users.py", 42), _bug("src/api/orders.py", 42))


def test_is_true_positive_path_normalisation_backslash() -> None:
    # Windows-style path in finding should normalise to match forward-slash path
    finding = _finding("src\\api\\users.py", 42)
    bug = _bug("src/api/users.py", 42)
    assert is_true_positive(finding, bug)


def test_is_true_positive_path_normalisation_leading_dot_slash() -> None:
    finding = _finding("./src/api/users.py", 42)
    bug = _bug("src/api/users.py", 42)
    assert is_true_positive(finding, bug)


# ---------------------------------------------------------------------------
# Tests: classify_findings
# ---------------------------------------------------------------------------


def test_classify_findings_all_true_positives() -> None:
    findings = [_finding("src/api/users.py", 42)]
    bugs = [_bug("src/api/users.py", 42)]
    tp, fp, fn = classify_findings(findings, bugs)
    assert tp == 1
    assert fp == 0
    assert fn == 0


def test_classify_findings_false_positive_only() -> None:
    findings = [_finding("src/api/users.py", 99)]
    bugs = [_bug("src/api/users.py", 42)]
    tp, fp, fn = classify_findings(findings, bugs)
    assert tp == 0
    assert fp == 1
    assert fn == 1


def test_classify_findings_false_negative_only() -> None:
    # No findings at all, one known bug
    tp, fp, fn = classify_findings([], [_bug("src/api/users.py", 42)])
    assert tp == 0
    assert fp == 0
    assert fn == 1


def test_classify_findings_empty_both() -> None:
    tp, fp, fn = classify_findings([], [])
    assert tp == 0
    assert fp == 0
    assert fn == 0


def test_classify_findings_bug_matched_at_most_once() -> None:
    # Two findings close to the same bug — only one TP, one FP
    findings = [_finding("src/a.py", 10), _finding("src/a.py", 11)]
    bugs = [_bug("src/a.py", 10)]
    tp, fp, fn = classify_findings(findings, bugs)
    assert tp == 1
    assert fp == 1
    assert fn == 0


def test_classify_findings_multiple_bugs_all_found() -> None:
    findings = [_finding("src/a.py", 10), _finding("src/b.py", 20)]
    bugs = [_bug("src/a.py", 10), _bug("src/b.py", 20)]
    tp, fp, fn = classify_findings(findings, bugs)
    assert tp == 2
    assert fp == 0
    assert fn == 0


# ---------------------------------------------------------------------------
# Tests: calculate_metrics
# ---------------------------------------------------------------------------


def test_calculate_metrics_perfect_precision_recall() -> None:
    results = [_result([_finding("src/a.py", 5)], [_bug("src/a.py", 5)])]
    metrics = calculate_metrics(results)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["noise_ratio"] == 0.0


def test_calculate_metrics_no_findings_gives_zero_recall() -> None:
    results = [_result([], [_bug("src/a.py", 5)])]
    metrics = calculate_metrics(results)
    assert metrics["recall"] == 0.0


def test_calculate_metrics_all_false_positives() -> None:
    results = [_result([_finding("src/a.py", 99)], [_bug("src/a.py", 5)])]
    metrics = calculate_metrics(results)
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["noise_ratio"] == 1.0


def test_calculate_metrics_skips_error_results() -> None:
    ok_result = _result([_finding("src/a.py", 5)], [_bug("src/a.py", 5)])
    error_result = _result([], [_bug("src/b.py", 10)], status="error")
    metrics = calculate_metrics([ok_result, error_result])
    # Error result is excluded — only the OK result counts
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_calculate_metrics_avg_latency() -> None:
    results = [
        _result([], [], latency_ms=1000),
        _result([], [], latency_ms=3000),
    ]
    metrics = calculate_metrics(results)
    assert metrics["avg_latency_ms"] == 2000


def test_calculate_metrics_p95_latency_single_value() -> None:
    results = [_result([], [], latency_ms=5000)]
    metrics = calculate_metrics(results)
    assert metrics["p95_latency_ms"] == 5000


def test_calculate_metrics_avg_cost() -> None:
    results = [
        _result([], [], cost_usd=0.01),
        _result([], [], cost_usd=0.03),
    ]
    metrics = calculate_metrics(results)
    assert abs(metrics["avg_cost_usd"] - 0.02) < 1e-6


def test_calculate_metrics_empty_results() -> None:
    metrics = calculate_metrics([])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["avg_latency_ms"] == 0
    assert metrics["avg_cost_usd"] == 0.0


# ---------------------------------------------------------------------------
# Tests: _safe_div / _percentile helpers
# ---------------------------------------------------------------------------


def test_safe_div_normal() -> None:
    assert _safe_div(3.0, 4.0) == pytest.approx(0.75)


def test_safe_div_zero_denominator() -> None:
    assert _safe_div(1.0, 0.0) == 0.0


def test_percentile_median() -> None:
    assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == pytest.approx(3.0)


def test_percentile_empty() -> None:
    assert _percentile([], 95) == 0.0


def test_percentile_single_value() -> None:
    assert _percentile([42.0], 95) == 42.0


# ---------------------------------------------------------------------------
# Tests: generate_report
# ---------------------------------------------------------------------------


def _make_raw_output(results: list[dict]) -> dict:
    return {
        "run_id": "2026-03-21T10-00-00",
        "provider": "openai",
        "model": "gpt-4o",
        "dataset_size": len(results),
        "results": results,
    }


def test_generate_report_returns_json_and_markdown() -> None:
    raw = _make_raw_output([_result([], [])])
    report = generate_report(raw)
    assert "json" in report
    assert "markdown" in report


def test_generate_report_json_has_required_keys() -> None:
    raw = _make_raw_output([_result([], [])])
    report = generate_report(raw)
    required_keys = {"run_id", "provider", "model", "dataset_size", "metrics", "per_pr_results"}
    assert required_keys.issubset(report["json"].keys())


def test_generate_report_json_metrics_keys() -> None:
    raw = _make_raw_output([_result([], [])])
    report = generate_report(raw)
    metrics = report["json"]["metrics"]
    expected = {
        "precision", "recall", "noise_ratio", "avg_latency_ms", "p95_latency_ms", "avg_cost_usd"
    }
    assert expected.issubset(metrics.keys())


def test_generate_report_json_is_serialisable() -> None:
    raw = _make_raw_output([_result([_finding("src/a.py", 5)], [_bug("src/a.py", 5)])])
    report = generate_report(raw)
    # Should not raise
    serialised = json.dumps(report["json"])
    assert len(serialised) > 0


def test_generate_report_markdown_contains_table_headers() -> None:
    raw = _make_raw_output([_result([], [])])
    report = generate_report(raw)
    md = report["markdown"]
    assert "Precision" in md
    assert "Recall" in md
    assert "Noise Ratio" in md
    assert "Avg Latency" in md
    assert "P95 Latency" in md
    assert "Avg Cost/Review" in md


def test_generate_report_markdown_contains_run_id() -> None:
    raw = _make_raw_output([_result([], [])])
    report = generate_report(raw)
    assert "2026-03-21T10-00-00" in report["markdown"]


def test_generate_report_markdown_contains_model() -> None:
    raw = _make_raw_output([_result([], [])])
    report = generate_report(raw)
    assert "gpt-4o" in report["markdown"]
