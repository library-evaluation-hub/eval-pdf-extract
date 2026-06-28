"""Runner: dispatch adapter subprocess calls.

Implements the orchestration flow described in adapter-protocol.md §5.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import psutil

from orchestrator.loader import load_json
from orchestrator.metrics.robustness import classify_exit_code
from orchestrator.models import AdapterEntry, FixtureEntry, RunResult

_DEFAULT_CONFIG: dict[str, Any] = {"ocr": {"enabled": True}}


def validate_result_schema(
    result: dict[str, Any],
    schema_path: Path,
) -> bool:
    """Validate result.json against result-schema.json."""
    try:
        from jsonschema import validate as js_validate

        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
        js_validate(instance=result, schema=schema)
        return True
    except Exception:
        return False


def _compute_output_size_kb(output_dir: Path) -> float:
    """Total size of all files in output_dir, in KB."""
    total = 0
    for root, _dirs, files in os.walk(output_dir):
        for fname in files:
            fpath = Path(root) / fname
            with contextlib.suppress(OSError):
                total += fpath.stat().st_size
    return total / 1024.0


def run_one(
    adapter: AdapterEntry,
    fixture: FixtureEntry,
    corpus_dir: Path,
    results_dir: Path,
    schema_path: Path,
    config: dict[str, Any] | None = None,
) -> RunResult:
    """Run a single (adapter, fixture) pair.

    1. Create output directory (clean if exists).
    2. Call adapter CLI as subprocess.
    3. Capture stdout/stderr, measure wall time + peak memory.
    4. Load and validate result.json.
    """
    fixture_dir = corpus_dir / "fixtures" / fixture.id
    input_pdf = fixture_dir / "input.pdf"

    output_dir = results_dir / adapter.id / fixture.id
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = config if config is not None else _DEFAULT_CONFIG
    timeout = adapter.timeout_seconds

    cmd = [
        adapter.command,
        "extract",
        "--input", str(input_pdf),
        "--output-dir", str(output_dir),
        "--config", json.dumps(cfg),
        "--timeout", str(timeout),
    ]

    start = time.monotonic()
    psutil_peak_mem: float | None = None

    try:
        p = psutil.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=os.name == "nt",
        )
        # Drain pipes on background threads to avoid deadlock when
        # adapter output exceeds OS pipe buffer (~64 KB).
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def _drain(pipe: Any, sink: list[str]) -> None:
            try:
                for chunk in iter(lambda: pipe.read(4096), ""):
                    sink.append(chunk)
            except (OSError, ValueError):
                pass

        stdout_thread = threading.Thread(
            target=_drain, args=(p.stdout, stdout_chunks), daemon=True
        )
        stderr_thread = threading.Thread(
            target=_drain, args=(p.stderr, stderr_chunks), daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()

        # Poll for memory usage until process exits or hard timeout
        hard_timeout = timeout + 5
        max_rss = 0
        deadline = time.monotonic() + hard_timeout
        timed_out = False

        # Sample memory immediately before any wait, so fast processes
        # still get at least one memory reading.
        try:
            mem_info = p.memory_info()
            if mem_info.rss > max_rss:
                max_rss = mem_info.rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        while p.poll() is None:
            if time.monotonic() > deadline:
                timed_out = True
                break
            try:
                mem_info = p.memory_info()
                if mem_info.rss > max_rss:
                    max_rss = mem_info.rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            try:
                p.wait(timeout=0.1)
            except (subprocess.TimeoutExpired, psutil.TimeoutExpired):
                continue

        if timed_out:
            with contextlib.suppress(psutil.NoSuchProcess):
                p.kill()
            with contextlib.suppress(psutil.NoSuchProcess, subprocess.TimeoutExpired, psutil.TimeoutExpired):
                p.wait(timeout=5)

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        exit_code = 124 if timed_out else p.returncode
        psutil_peak_mem = max_rss / (1024 * 1024) if max_rss > 0 else None
    except FileNotFoundError:
        stdout = ""
        stderr = f"command '{adapter.command}' not found in PATH"
        exit_code = 127
    except Exception as e:
        stdout = ""
        stderr = f"runner error: {type(e).__name__}: {e}"
        exit_code = 1

    wall_ms = int((time.monotonic() - start) * 1000)

    # Write stdout.log and stderr.log
    (output_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (output_dir / "stderr.log").write_text(stderr, encoding="utf-8")

    # Load result.json
    result_path = output_dir / "result.json"
    has_result = result_path.exists()
    result_data = load_json(result_path)
    result_valid = False
    if result_data is not None:
        result_valid = validate_result_schema(result_data, schema_path)

    # Load meta.json
    meta_data = load_json(output_dir / "meta.json")

    # Per metric-spec.md §3.3: prefer adapter self-reported peak memory,
    # fall back to psutil measurement.
    peak_mem: float | None = None
    if meta_data:
        exec_info = meta_data.get("execution", {})
        peak_mem = exec_info.get("peak_memory_mb_self")
    if peak_mem is None:
        peak_mem = psutil_peak_mem

    output_size = _compute_output_size_kb(output_dir)
    error_category = classify_exit_code(exit_code, has_result)

    return RunResult(
        adapter_id=adapter.id,
        fixture_id=fixture.id,
        exit_code=exit_code,
        wall_time_ms=wall_ms,
        peak_memory_mb=peak_mem,
        output_size_kb=output_size,
        output_dir=output_dir,
        stdout=stdout,
        stderr=stderr,
        has_result=has_result,
        result_valid=result_valid,
        error_category=error_category,
        result_data=result_data if result_valid else None,
        meta_data=meta_data,
    )
