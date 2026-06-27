"""Store: persist run artifacts to results/<run_id>/.

Creates the directory structure described in ARCHITECTURE.md §7.2:

    results/<run_id>/
    ├── run.json
    ├── scores.csv
    ├── scores.db
    ├── summary.json
    └── <adapter_id>/<fixture_id>/
        ├── result.json       (written by adapter)
        ├── meta.json         (written by adapter)
        ├── stdout.log
        ├── stderr.log
        ├── timings.json
        └── score.json
"""

from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from orchestrator.models import (
    ALL_METRIC_IDS,
    RunResult,
    ScoreResult,
)


def init_run_dir(results_root: Path, run_id: str) -> Path:
    """Create results/<run_id>/ directory. Returns the path."""
    run_dir = results_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run_json(
    run_dir: Path,
    run_id: str,
    config: dict[str, Any],
) -> None:
    """Write run.json with run configuration and metadata."""
    run_meta = {
        "run_id": run_id,
        "config": config,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }
    (run_dir / "run.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_timings(run_result: RunResult) -> dict[str, Any]:
    """Write timings.json for a single run result. Returns the timings dict."""
    timings = {
        "wall_time_ms": run_result.wall_time_ms,
        "peak_memory_mb": run_result.peak_memory_mb,
        "output_size_kb": run_result.output_size_kb,
        "exit_code": run_result.exit_code,
    }
    timings_path = run_result.output_dir / "timings.json"
    timings_path.write_text(
        json.dumps(timings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return timings


def write_score_json(
    run_dir: Path,
    score_result: ScoreResult,
) -> None:
    """Write score.json to the correct location under run_dir."""
    score_path = (
        run_dir
        / score_result.adapter_id
        / score_result.fixture_id
        / "score.json"
    )
    score_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "adapter_id": score_result.adapter_id,
        "fixture_id": score_result.fixture_id,
        "fixture_category": score_result.fixture_category,
        "metrics": score_result.metrics,
        "skipped_metrics": score_result.skipped_metrics,
    }
    score_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_scores_csv(
    run_dir: Path,
    all_scores: list[ScoreResult],
) -> None:
    """Write scores.csv — long table: adapter, fixture, metric, value."""
    csv_path = run_dir / "scores.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["adapter_id", "fixture_id", "fixture_category", "metric", "value"])
        for sr in all_scores:
            for metric_id in ALL_METRIC_IDS:
                value = sr.metrics.get(metric_id)
                writer.writerow([
                    sr.adapter_id,
                    sr.fixture_id,
                    sr.fixture_category,
                    metric_id,
                    "" if value is None else value,
                ])


def write_scores_db(
    run_dir: Path,
    all_scores: list[ScoreResult],
) -> None:
    """Write scores.db — sqlite with scores table + indexes."""
    db_path = run_dir / "scores.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE scores (
            adapter_id    TEXT NOT NULL,
            fixture_id    TEXT NOT NULL,
            fixture_category TEXT NOT NULL,
            metric        TEXT NOT NULL,
            value         REAL,
            value_text    TEXT,
            skipped       INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX idx_scores_adapter ON scores(adapter_id)
    """)
    conn.execute("""
        CREATE INDEX idx_scores_fixture ON scores(fixture_id)
    """)
    conn.execute("""
        CREATE INDEX idx_scores_metric ON scores(metric)
    """)

    for sr in all_scores:
        for metric_id in ALL_METRIC_IDS:
            value = sr.metrics.get(metric_id)
            is_skipped = metric_id in sr.skipped_metrics or value is None
            val: float | None = None
            val_text: str | None = None
            if isinstance(value, bool):
                val = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                val = float(value)
            elif isinstance(value, str):
                val_text = value
            conn.execute(
                "INSERT INTO scores VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sr.adapter_id, sr.fixture_id, sr.fixture_category,
                 metric_id, val, val_text, 1 if is_skipped else 0),
            )
    conn.commit()
    conn.close()


def finalize_run_json(
    run_dir: Path,
    run_id: str,
    config: dict[str, Any],
    total_pairs: int,
    completed: int,
    failed: int,
) -> None:
    """Update run.json with completion info, preserving started_at."""
    run_json_path = run_dir / "run.json"
    existing: dict[str, Any] = {}
    if run_json_path.exists():
        try:
            with run_json_path.open("r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    run_meta: dict[str, Any] = {
        "run_id": run_id,
        "config": config,
        "started_at": existing.get("started_at", ""),
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "total_pairs": total_pairs,
        "completed": completed,
        "failed": failed,
    }
    run_json_path.write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
