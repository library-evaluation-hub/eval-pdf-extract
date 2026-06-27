"""Shared test fixtures and helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orchestrator.models import RunResult


def make_page(
    page_number: int,
    text: str = "",
    blocks: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    width: float = 612.0,
    height: float = 792.0,
) -> dict[str, Any]:
    """Build a minimal page dict conforming to result-schema.json."""
    return {
        "page_number": page_number,
        "width": width,
        "height": height,
        "text": text,
        "blocks": blocks or [],
        "tables": tables or [],
    }


def make_block(
    block_id: str,
    btype: str,
    bbox: list[float],
    content: str = "",
    reading_order: int = 0,
    level: int | None = None,
) -> dict[str, Any]:
    """Build a minimal block dict."""
    b: dict[str, Any] = {
        "id": block_id,
        "type": btype,
        "bbox": bbox,
        "content": content,
        "reading_order": reading_order,
    }
    if level is not None:
        b["level"] = level
    return b


def make_table(
    bbox: list[float],
    rows: list[list[str]],
    headers: list[str] | None = None,
    table_id: str = "t1",
) -> dict[str, Any]:
    """Build a minimal table dict."""
    t: dict[str, Any] = {
        "id": table_id,
        "bbox": bbox,
        "rows": rows,
    }
    if headers is not None:
        t["headers"] = headers
    return t


def make_result(
    pages: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a result-schema-compliant dict."""
    return {
        "schema_version": "1.0.0",
        "metadata": metadata or {
            "title": None,
            "author": None,
            "subject": None,
            "keywords": None,
            "creator": None,
            "producer": None,
            "page_count": len(pages),
            "ocr_used": False,
        },
        "pages": pages,
    }


def make_run_result_fn(
    adapter_id: str = "test-adapter@1.0.0",
    fixture_id: str = "01_plain_text__test",
    exit_code: int = 0,
    result_data: dict[str, Any] | None = None,
    result_valid: bool | None = None,
    has_result: bool = True,
    wall_time_ms: int = 100,
    peak_memory_mb: float | None = 50.0,
    output_size_kb: float = 1.0,
    output_dir: Path | None = None,
    error_category: str = "none",
) -> RunResult:
    """Build a RunResult for testing.

    If result_valid is None, it defaults to (result_data is not None),
    matching runner behavior where validity requires data to exist.

    output_dir must be provided by the caller (e.g. via the make_run_result
    fixture or tmp_path). There is no default — this prevents temp dir leaks.
    """
    if result_valid is None:
        result_valid = result_data is not None
    if output_dir is None:
        raise ValueError("output_dir is required — use the make_run_result fixture or pass tmp_path")
    return RunResult(
        adapter_id=adapter_id,
        fixture_id=fixture_id,
        exit_code=exit_code,
        wall_time_ms=wall_time_ms,
        peak_memory_mb=peak_memory_mb,
        output_size_kb=output_size_kb,
        output_dir=output_dir,
        stdout="",
        stderr="",
        has_result=has_result,
        result_valid=result_valid,
        error_category=error_category,
        result_data=result_data,
        meta_data=None,
    )


@pytest.fixture
def make_run_result(tmp_path: Path):
    """Factory: build a RunResult with output_dir under tmp_path (auto-cleaned)."""
    def _make(
        adapter_id: str = "test-adapter@1.0.0",
        fixture_id: str = "01_plain_text__test",
        exit_code: int = 0,
        result_data: dict[str, Any] | None = None,
        result_valid: bool | None = None,
        has_result: bool = True,
        wall_time_ms: int = 100,
        peak_memory_mb: float | None = 50.0,
        output_size_kb: float = 1.0,
        error_category: str = "none",
    ) -> RunResult:
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return make_run_result_fn(
            adapter_id=adapter_id,
            fixture_id=fixture_id,
            exit_code=exit_code,
            result_data=result_data,
            result_valid=result_valid,
            has_result=has_result,
            wall_time_ms=wall_time_ms,
            peak_memory_mb=peak_memory_mb,
            output_size_kb=output_size_kb,
            output_dir=output_dir,
            error_category=error_category,
        )
    return _make


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Provide a temporary output directory."""
    d = tmp_path / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def sample_result_json() -> dict[str, Any]:
    """A minimal valid result.json for schema validation tests."""
    return make_result([
        make_page(1, text="Hello World"),
    ])


@pytest.fixture
def result_schema_path() -> Path:
    """Path to contract/result-schema.json."""
    return Path(__file__).resolve().parent.parent / "contract" / "result-schema.json"


@pytest.fixture
def write_result_json(tmp_output_dir: Path):
    """Factory: write a result.json into tmp_output_dir and return its path."""
    def _write(data: dict[str, Any]) -> Path:
        p = tmp_output_dir / "result.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return p
    return _write
