"""Report: generate summary.json with per-adapter x per-category aggregation.

Implements the aggregation strategy from metric-spec.md §4:
- macro-average within each category
- overall macro-average across all fixtures
- skipped metrics excluded from averages
- performance metrics aggregated separately (overall only)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestrator.models import (
    ALL_METRIC_IDS,
    METRIC_CATEGORIES,
    ScoreResult,
)

# Performance metrics get overall-only aggregation
_PERFORMANCE_METRICS = {
    m for m, cat in METRIC_CATEGORIES.items() if cat == "performance"
}

# Robustness metrics: success is bool, error_category is enum
# For aggregation, success → mean (proportion), error_category → mode (skip)
_AGGREGATABLE_METRICS = {
    m for m in ALL_METRIC_IDS
    if METRIC_CATEGORIES[m] != "robustness"
    or m in {"success", "partial_completion_ratio"}
}


def generate_summary(
    all_scores: list[ScoreResult],
    run_dir: Path,
) -> dict[str, Any]:
    """Generate and write summary.json.

    Structure:
    {
        "per_adapter": {
            "<adapter_id>": {
                "per_category": {
                    "text": { "text_cer": avg, ... },
                    "structure": { ... },
                    "performance": { ... },
                    "robustness": { "success": avg, ... }
                },
                "per_metric_overall": { "text_cer": avg, ... }
            }
        }
    }
    """
    # Group scores by adapter
    by_adapter: dict[str, list[ScoreResult]] = {}
    for sr in all_scores:
        by_adapter.setdefault(sr.adapter_id, []).append(sr)

    per_adapter: dict[str, Any] = {}

    for adapter_id, scores in by_adapter.items():
        # Group by metric category (text, structure, performance, robustness)
        # per metric-spec.md §4
        metric_categories = ["text", "structure", "performance", "robustness"]
        per_category: dict[str, dict[str, float | None]] = {}
        all_metric_values: dict[str, list[float]] = {}

        for mcat in metric_categories:
            cat_metric_ids = {
                m for m in ALL_METRIC_IDS if METRIC_CATEGORIES[m] == mcat
            }
            cat_metrics: dict[str, float | None] = {}

            for metric_id in cat_metric_ids:
                if metric_id not in _AGGREGATABLE_METRICS:
                    continue

                values: list[float] = []
                for sr in scores:
                    if metric_id in sr.skipped_metrics:
                        continue
                    val = sr.metrics.get(metric_id)
                    if val is None:
                        continue
                    if isinstance(val, bool):
                        values.append(1.0 if val else 0.0)
                    elif isinstance(val, (int, float)):
                        values.append(float(val))

                if values:
                    avg = sum(values) / len(values)
                    cat_metrics[metric_id] = avg
                    all_metric_values.setdefault(metric_id, []).extend(values)
                else:
                    cat_metrics[metric_id] = None

            per_category[mcat] = cat_metrics

        # Per-metric overall (macro across all fixtures)
        per_metric_overall: dict[str, float | None] = {}
        for metric_id in ALL_METRIC_IDS:
            if metric_id not in _AGGREGATABLE_METRICS:
                continue
            values = all_metric_values.get(metric_id, [])
            if values:
                per_metric_overall[metric_id] = sum(values) / len(values)
            else:
                per_metric_overall[metric_id] = None

        per_adapter[adapter_id] = {
            "per_category": per_category,
            "per_metric_overall": per_metric_overall,
        }

    summary = {"per_adapter": per_adapter}

    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return summary
