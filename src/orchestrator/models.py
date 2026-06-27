"""Data models for orchestrator.

Defines dataclasses for adapter registry entries, corpus fixture entries,
run results, and score results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AdapterEntry:
    """One entry from adapters/registry.json."""

    id: str
    command: str
    language: str
    timeout_seconds: int = 60
    supports_ocr: bool = False
    disabled: bool = False


@dataclass(frozen=True)
class FixtureEntry:
    """One entry from corpus/manifest.json."""

    id: str
    path: str
    category: str
    expected_page_count: int
    sha256: str
    tags: list[str] = field(default_factory=list)
    difficulty: str | None = None


@dataclass
class RunResult:
    """Result of running a single (adapter, fixture) pair."""

    adapter_id: str
    fixture_id: str
    exit_code: int
    wall_time_ms: int
    peak_memory_mb: float | None
    output_size_kb: float
    output_dir: Path
    stdout: str
    stderr: str
    has_result: bool
    result_valid: bool
    error_category: str
    result_data: dict[str, Any] | None = None
    meta_data: dict[str, Any] | None = None


@dataclass
class ScoreResult:
    """Scores for a single (adapter, fixture) pair."""

    adapter_id: str
    fixture_id: str
    fixture_category: str
    metrics: dict[str, Any]
    skipped_metrics: list[str] = field(default_factory=list)


ALL_METRIC_IDS: tuple[str, ...] = (
    "text_cer",
    "text_wer",
    "text_exact_page_match_ratio",
    "table_detection_f1",
    "table_cell_value_f1",
    "heading_detection_f1",
    "reading_order_kendall_tau",
    "wall_time_ms",
    "peak_memory_mb",
    "output_size_kb",
    "success",
    "partial_completion_ratio",
    "error_category",
)

METRIC_CATEGORIES: dict[str, str] = {
    "text_cer": "text",
    "text_wer": "text",
    "text_exact_page_match_ratio": "text",
    "table_detection_f1": "structure",
    "table_cell_value_f1": "structure",
    "heading_detection_f1": "structure",
    "reading_order_kendall_tau": "structure",
    "wall_time_ms": "performance",
    "peak_memory_mb": "performance",
    "output_size_kb": "performance",
    "success": "robustness",
    "partial_completion_ratio": "robustness",
    "error_category": "robustness",
}
