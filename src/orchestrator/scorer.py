"""Scorer: compute all 13 metrics for a (RunResult, expected) pair.

Implements the scoring logic defined in contract/metric-spec.md.
"""

from __future__ import annotations

from typing import Any

from orchestrator.metrics import (
    cer,
    classify_exit_code,
    compute_success,
    exact_page_match,
    heading_detection_f1,
    partial_completion_ratio,
    reading_order_kendall_tau,
    table_cell_value_f1,
    table_detection_f1,
    wer,
)
from orchestrator.models import RunResult, ScoreResult


def _align_pages_by_number(
    result_pages: list[dict[str, Any]],
    expected_pages: list[dict[str, Any]],
) -> list[tuple[dict[str, Any] | None, dict[str, Any] | None]]:
    """Align pages by page_number. Returns list of (result_page, expected_page)."""
    result_map: dict[Any, dict[str, Any]] = {p.get("page_number"): p for p in result_pages}
    expected_map: dict[Any, dict[str, Any]] = {p.get("page_number"): p for p in expected_pages}
    all_nums = sorted(set(result_map.keys()) | set(expected_map.keys()))
    return [
        (result_map.get(n), expected_map.get(n)) for n in all_nums
    ]


def score(
    run_result: RunResult,
    expected: dict[str, Any],
    fixture_category: str,
) -> ScoreResult:
    """Compute all 13 metrics for a single run result.

    Args:
        run_result: The RunResult from runner.run_one().
        expected: The ground truth dict (expected.json).
        fixture_category: The category of the fixture (e.g. 'plain_text').

    Returns:
        ScoreResult with all metric values and list of skipped metrics.
    """
    metrics: dict[str, Any] = {}
    skipped: list[str] = []

    expected_pages = expected.get("pages", [])
    expected_meta = expected.get("metadata", {})
    expected_page_count = expected_meta.get("page_count", len(expected_pages))

    # --- Robustness metrics ---
    result_pages: list[dict[str, Any]] = []
    result_page_count = 0
    if run_result.result_data is not None:
        result_pages = run_result.result_data.get("pages", [])
        result_page_count = len(result_pages)
        result_meta = run_result.result_data.get("metadata", {})
        if result_meta.get("page_count") is not None:
            result_page_count = result_meta["page_count"]

    metrics["success"] = compute_success(
        exit_code=run_result.exit_code,
        has_result=run_result.has_result,
        result_valid=run_result.result_valid,
        result_page_count=result_page_count,
        expected_page_count=expected_page_count,
    )
    metrics["partial_completion_ratio"] = partial_completion_ratio(
        result_page_count=result_page_count,
        expected_page_count=expected_page_count,
    )
    metrics["error_category"] = classify_exit_code(
        run_result.exit_code, run_result.has_result
    )

    # --- Performance metrics ---
    metrics["wall_time_ms"] = run_result.wall_time_ms
    metrics["peak_memory_mb"] = run_result.peak_memory_mb
    metrics["output_size_kb"] = run_result.output_size_kb

    # --- Text & structure metrics (only if result is valid) ---
    if run_result.result_data is not None and run_result.result_valid:
        _score_text_and_structure(
            result_pages, expected_pages, expected_page_count,
            metrics, skipped,
        )
    else:
        # Result not available or invalid — skip text/structure metrics
        for m in (
            "text_cer", "text_wer", "text_exact_page_match_ratio",
            "table_detection_f1", "table_cell_value_f1",
            "heading_detection_f1", "reading_order_kendall_tau",
        ):
            skipped.append(m)
            metrics[m] = None

    return ScoreResult(
        adapter_id=run_result.adapter_id,
        fixture_id=run_result.fixture_id,
        fixture_category=fixture_category,
        metrics=metrics,
        skipped_metrics=skipped,
    )


def _score_text_and_structure(
    result_pages: list[dict[str, Any]],
    expected_pages: list[dict[str, Any]],
    expected_page_count: int,
    metrics: dict[str, Any],
    skipped: list[str],
) -> None:
    """Compute text and structure metrics, populating metrics dict in-place."""
    # Handle zero-page case
    if expected_page_count == 0 and len(expected_pages) == 0:
        if len(result_pages) == 0:
            metrics["text_cer"] = 0.0
            metrics["text_wer"] = 0.0
            metrics["text_exact_page_match_ratio"] = 1.0
        else:
            metrics["text_cer"] = 1.0
            metrics["text_wer"] = 1.0
            metrics["text_exact_page_match_ratio"] = 0.0
        # Structure metrics skipped for zero-page
        for m in (
            "table_detection_f1", "table_cell_value_f1",
            "heading_detection_f1", "reading_order_kendall_tau",
        ):
            skipped.append(m)
            metrics[m] = None
        return

    # --- Text metrics ---
    aligned = _align_pages_by_number(result_pages, expected_pages)
    cer_scores: list[float] = []
    wer_scores: list[float] = []
    exact_matches = 0
    total_pages = 0

    for res_page, exp_page in aligned:
        if exp_page is None:
            # Result has extra page not in expected — count as mismatch
            total_pages += 1
            continue
        if res_page is None:
            # Expected page missing from result — count as mismatch
            total_pages += 1
            ref_text = exp_page.get("text", "")
            cer_scores.append(1.0 if len(ref_text) > 0 else 0.0)
            wer_scores.append(1.0 if len(ref_text) > 0 else 0.0)
            continue

        total_pages += 1
        ref_text = exp_page.get("text", "")
        hyp_text = res_page.get("text", "")
        cer_scores.append(cer(ref_text, hyp_text))
        wer_scores.append(wer(ref_text, hyp_text))
        if exact_page_match(ref_text, hyp_text):
            exact_matches += 1

    metrics["text_cer"] = (
        sum(cer_scores) / len(cer_scores) if cer_scores else 0.0
    )
    metrics["text_wer"] = (
        sum(wer_scores) / len(wer_scores) if wer_scores else 0.0
    )
    metrics["text_exact_page_match_ratio"] = (
        exact_matches / total_pages if total_pages > 0 else 1.0
    )

    # --- Structure metrics ---
    val = table_detection_f1(result_pages, expected_pages)
    if val is None:
        skipped.append("table_detection_f1")
        metrics["table_detection_f1"] = None
    else:
        metrics["table_detection_f1"] = val

    val = table_cell_value_f1(result_pages, expected_pages)
    if val is None:
        skipped.append("table_cell_value_f1")
        metrics["table_cell_value_f1"] = None
    else:
        metrics["table_cell_value_f1"] = val

    val = heading_detection_f1(result_pages, expected_pages)
    if val is None:
        skipped.append("heading_detection_f1")
        metrics["heading_detection_f1"] = None
    else:
        metrics["heading_detection_f1"] = val

    val = reading_order_kendall_tau(result_pages, expected_pages)
    if val is None:
        skipped.append("reading_order_kendall_tau")
        metrics["reading_order_kendall_tau"] = None
    else:
        metrics["reading_order_kendall_tau"] = val
