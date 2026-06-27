"""Metrics package — re-exports all metric implementations.

See contract/metric-spec.md for the full specification.
"""

from orchestrator.metrics.robustness import (
    classify_exit_code,
    compute_success,
    partial_completion_ratio,
)
from orchestrator.metrics.structure import (
    heading_detection_f1,
    iou,
    kendall_tau_b,
    reading_order_kendall_tau,
    table_cell_value_f1,
    table_detection_f1,
)
from orchestrator.metrics.text import (
    cer,
    exact_page_match,
    levenshtein,
    levenshtein_tokens,
    normalize_text,
    wer,
)

__all__ = [
    "cer",
    "classify_exit_code",
    "compute_success",
    "exact_page_match",
    "heading_detection_f1",
    "iou",
    "kendall_tau_b",
    "levenshtein",
    "levenshtein_tokens",
    "normalize_text",
    "partial_completion_ratio",
    "reading_order_kendall_tau",
    "table_cell_value_f1",
    "table_detection_f1",
    "wer",
]
