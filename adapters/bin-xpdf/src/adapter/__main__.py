"""Xpdf pdftotext adapter for eval-pdf-extract.

Wraps the pdftotext binary to implement the adapter protocol.
pdftotext outputs plain text with form-feed (\\f) page separators.
This wrapper converts that to result-schema.json format.

Known limitations:
- No block-level structure (blocks left empty; only page text is populated).
- No table extraction.
- No metadata extraction (pdftotext does not provide document metadata).
- Page dimensions not available from pdftotext output.
- timeout: accepted but not enforced.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _find_pdftotext() -> Path:
    """Locate the pdftotext binary relative to this package."""
    # The binary ships alongside this adapter in adapters/bin-xpdf/
    # __file__ is at .../adapters/bin-xpdf/src/adapter/__main__.py
    # parents[2] = .../adapters/bin-xpdf/
    adapter_root = Path(__file__).resolve().parents[2]
    candidates = [
        adapter_root / "pdftotext.exe",
        adapter_root / "pdftotext",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fallback: hope it's on PATH
    return Path("pdftotext")


def _extract(
    input_pdf: Path,
    output_dir: Path,
    config: dict[str, Any],
    timeout: int,
) -> int:
    if not input_pdf.exists():
        print(f"input not found: {input_pdf}", file=sys.stderr)
        return 64

    binary = _find_pdftotext()
    t0 = time.monotonic()

    # pdftotext writes to stdout when output file is "-"
    # -enc UTF-8 ensures unicode output; -eol unix for consistent newlines
    proc = subprocess.run(
        [str(binary), "-enc", "UTF-8", "-eol", "unix", str(input_pdf), "-"],
        capture_output=True,
        timeout=timeout + 5,
    )

    if proc.returncode != 0:
        stderr_msg = proc.stderr.decode("utf-8", errors="replace").strip()
        print(f"pdftotext failed (exit {proc.returncode}): {stderr_msg}", file=sys.stderr)
        # Map pdftotext exit codes to adapter protocol exit codes
        # 1 = error opening PDF → 64 (unsupported)
        # 98 = out of memory → 66 (oom)
        # 2, 3, 99 = other errors → 65 (parse_error)
        if proc.returncode == 1:
            return 64
        if proc.returncode == 98:
            return 66
        return 65

    raw = proc.stdout.decode("utf-8", errors="replace")

    # Split by form-feed (\f) into pages
    # pdftotext inserts \f at end of each page (except possibly the last)
    raw_pages = raw.split("\f")
    # Remove trailing empty page if the text ended with \f
    if raw_pages and raw_pages[-1].strip() == "":
        raw_pages.pop()

    pages: list[dict[str, Any]] = []
    for i, page_text in enumerate(raw_pages):
        pages.append({
            "page_number": i + 1,
            "text": page_text.strip(),
            "blocks": [],
            "tables": [],
        })

    wall_ms_self = (time.monotonic() - t0) * 1000

    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "metadata": {
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

    result_path = output_dir / "result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Extract version from binary output
    version = "4.06"
    try:
        ver_proc = subprocess.run(
            [str(binary), "-v"],
            capture_output=True,
            timeout=10,
        )
        ver_text = (ver_proc.stderr or ver_proc.stdout).decode("utf-8", errors="replace")
        import re
        m = re.search(r"version\s+([\d.]+)", ver_text)
        if m:
            version = m.group(1)
    except Exception:
        pass

    meta_out: dict[str, Any] = {
        "library": {
            "name": "Xpdf pdftotext",
            "version": version,
            "language": "binary",
        },
        "execution": {
            "ocr_used": False,
            "ocr_engine": None,
            "wall_time_ms_self": round(wall_ms_self, 1),
            "peak_memory_mb_self": None,
        },
        "warnings": [],
    }
    (output_dir / "meta.json").write_text(
        json.dumps(meta_out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="bin-xpdf")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--input", required=True, type=Path)
    e.add_argument("--output-dir", required=True, type=Path)
    e.add_argument("--config", default="{}")
    e.add_argument("--timeout", type=int, default=60)
    args = p.parse_args()

    if args.cmd == "extract":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            config = json.loads(args.config)
        except json.JSONDecodeError:
            print("invalid --config JSON", file=sys.stderr)
            return 2
        try:
            return _extract(args.input, args.output_dir, config, args.timeout)
        except FileNotFoundError:
            print(f"input not found: {args.input}", file=sys.stderr)
            return 64
        except subprocess.TimeoutExpired:
            print("pdftotext timed out", file=sys.stderr)
            return 124
        except Exception as exc:
            print(f"extract failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 65
    return 2


if __name__ == "__main__":
    sys.exit(main())
