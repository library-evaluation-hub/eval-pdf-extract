"""Robustness metrics: success, partial_completion_ratio, error_category.

Implements the algorithms defined in contract/metric-spec.md §3.4.
"""

from __future__ import annotations

_EXIT_CODE_MAP: dict[int, str] = {
    0: "none",
    2: "bad_args",
    64: "unsupported",
    65: "parse_error",
    66: "oom",
    124: "timeout",
}


def classify_exit_code(exit_code: int, has_result: bool) -> str:
    """Map exit code to error category per adapter-protocol.md §3."""
    if exit_code == 0:
        return "none"
    return _EXIT_CODE_MAP.get(exit_code, "crash")


def compute_success(
    exit_code: int,
    has_result: bool,
    result_valid: bool,
    result_page_count: int,
    expected_page_count: int,
) -> bool:
    """True iff exit_code==0, result.json exists+valid, page count matches."""
    return (
        exit_code == 0
        and has_result
        and result_valid
        and result_page_count == expected_page_count
    )


def partial_completion_ratio(
    result_page_count: int,
    expected_page_count: int,
) -> float:
    """Ratio of completed pages.

    See metric-spec.md §3.5 for zero-page edge cases.
    """
    if expected_page_count == 0:
        return 1.0 if result_page_count == 0 else 0.0
    return min(result_page_count, expected_page_count) / expected_page_count
