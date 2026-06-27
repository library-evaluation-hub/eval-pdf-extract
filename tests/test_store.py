"""Unit tests for store: init_run_dir, write_timings, write_score_json,
write_scores_csv, write_scores_db."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from orchestrator.models import ScoreResult
from orchestrator.store import (
    finalize_run_json,
    init_run_dir,
    write_run_json,
    write_score_json,
    write_scores_csv,
    write_scores_db,
    write_timings,
)
from tests.conftest import make_run_result_fn


def _make_score_result(
    adapter_id: str = "test-adapter@1.0.0",
    fixture_id: str = "01_plain_text__test",
    metrics: dict[str, Any] | None = None,
    skipped: list[str] | None = None,
) -> ScoreResult:
    return ScoreResult(
        adapter_id=adapter_id,
        fixture_id=fixture_id,
        fixture_category="plain_text",
        metrics=metrics or {
            "text_cer": 0.1,
            "text_wer": 0.2,
            "text_exact_page_match_ratio": 0.8,
            "table_detection_f1": None,
            "table_cell_value_f1": None,
            "heading_detection_f1": None,
            "reading_order_kendall_tau": None,
            "wall_time_ms": 100,
            "peak_memory_mb": 50.0,
            "output_size_kb": 1.5,
            "success": True,
            "partial_completion_ratio": 1.0,
            "error_category": "none",
        },
        skipped_metrics=skipped or [
            "table_detection_f1",
            "table_cell_value_f1",
            "heading_detection_f1",
            "reading_order_kendall_tau",
        ],
    )


class TestInitRunDir:
    def test_creates_dir(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run-001")
        assert run_dir.exists()
        assert run_dir.name == "test-run-001"

    def test_idempotent(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run-001")
        # Second call should not fail
        run_dir2 = init_run_dir(tmp_path, "test-run-001")
        assert run_dir == run_dir2


class TestWriteRunJson:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        config = {"adapters": "all", "workers": 4}
        write_run_json(run_dir, "test-run", config)

        data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert data["run_id"] == "test-run"
        assert data["config"] == config
        assert "started_at" in data


class TestFinalizeRunJson:
    def test_preserves_started_at(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        write_run_json(run_dir, "test-run", {})
        # Capture original started_at value
        original = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        original_started_at = original["started_at"]

        finalize_run_json(run_dir, "test-run", {}, total_pairs=5, completed=4, failed=1)

        data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert data["total_pairs"] == 5
        assert data["completed"] == 4
        assert data["failed"] == 1
        assert data["started_at"] == original_started_at
        assert data["started_at"] != ""
        assert "completed_at" in data


class TestWriteTimings:
    def test_writes_timings(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        rr = make_run_result_fn(
            wall_time_ms=200,
            peak_memory_mb=75.0,
            output_size_kb=2.5,
            output_dir=output_dir,
        )
        timings = write_timings(rr)
        assert timings["wall_time_ms"] == 200
        assert timings["peak_memory_mb"] == 75.0
        assert timings["output_size_kb"] == 2.5

        data = json.loads((output_dir / "timings.json").read_text(encoding="utf-8"))
        assert data["wall_time_ms"] == 200


class TestWriteScoreJson:
    def test_writes_score(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        sr = _make_score_result()
        write_score_json(run_dir, sr)

        score_path = run_dir / sr.adapter_id / sr.fixture_id / "score.json"
        assert score_path.exists()
        data = json.loads(score_path.read_text(encoding="utf-8"))
        assert data["adapter_id"] == sr.adapter_id
        assert data["fixture_id"] == sr.fixture_id
        assert data["metrics"]["text_cer"] == 0.1


class TestWriteScoresCsv:
    def test_writes_csv(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        scores = [_make_score_result(), _make_score_result(fixture_id="02_multi_column__test2")]
        write_scores_csv(run_dir, scores)

        csv_path = run_dir / "scores.csv"
        assert csv_path.exists()
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["adapter_id", "fixture_id", "fixture_category", "metric", "value"]
            rows = list(reader)
            # 2 score results x 13 metrics = 26 rows
            assert len(rows) == 26

    def test_none_values_as_empty(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        sr = _make_score_result()
        write_scores_csv(run_dir, [sr])

        csv_path = run_dir / "scores.csv"
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)
            # Find the table_detection_f1 row (should have empty value)
            td_rows = [r for r in rows if r[3] == "table_detection_f1"]
            assert len(td_rows) == 1
            assert td_rows[0][4] == ""


class TestWriteScoresDb:
    def test_creates_db(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        scores = [_make_score_result()]
        write_scores_db(run_dir, scores)

        db_path = run_dir / "scores.db"
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM scores")
        assert cursor.fetchone()[0] == 13  # 13 metrics per score result
        conn.close()

    def test_skipped_flag(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        sr = _make_score_result()
        write_scores_db(run_dir, [sr])

        db_path = run_dir / "scores.db"
        conn = sqlite3.connect(str(db_path))
        # table_detection_f1 should be skipped=1
        cursor = conn.execute(
            "SELECT skipped FROM scores WHERE metric = 'table_detection_f1'"
        )
        assert cursor.fetchone()[0] == 1
        # text_cer should not be skipped
        cursor = conn.execute(
            "SELECT skipped FROM scores WHERE metric = 'text_cer'"
        )
        assert cursor.fetchone()[0] == 0
        conn.close()

    def test_overwrites_existing_db(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        write_scores_db(run_dir, [_make_score_result()])
        # Second write should replace, not append
        write_scores_db(run_dir, [_make_score_result()])

        db_path = run_dir / "scores.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM scores")
        assert cursor.fetchone()[0] == 13
        conn.close()

    def test_bool_stored_as_numeric(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        sr = _make_score_result()
        write_scores_db(run_dir, [sr])

        db_path = run_dir / "scores.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT value, value_text FROM scores WHERE metric = 'success'"
        )
        row = cursor.fetchone()
        assert row[0] == 1.0  # True → 1.0
        assert row[1] is None
        conn.close()

    def test_string_metric_stored_as_text(self, tmp_path: Path) -> None:
        run_dir = init_run_dir(tmp_path, "test-run")
        sr = _make_score_result()
        write_scores_db(run_dir, [sr])

        db_path = run_dir / "scores.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT value, value_text FROM scores WHERE metric = 'error_category'"
        )
        row = cursor.fetchone()
        assert row[0] is None  # numeric value is NULL
        assert row[1] == "none"  # stored as text
        conn.close()
