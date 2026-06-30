"""pdfplumber adapter for eval-pdf-extract.

CLI entry point implementing the adapter protocol (contract/adapter-protocol.md).

Known gaps:
- timeout: accepted but not enforced; the orchestrator's hard timeout
  (timeout + 5s) is the backstop. Self-termination is not implemented.
- config: accepted but ignored; options like ocr.enabled, max_pages
  have no effect. All pages are always extracted without OCR.
- blocks: pdfplumber does not provide block-level structure; blocks are
  approximated from extracted words grouped by lines.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def _extract(
    input_pdf: Path,
    output_dir: Path,
    config: dict[str, Any],
    timeout: int,
) -> int:
    import pdfplumber

    if not input_pdf.exists():
        print(f"input not found: {input_pdf}", file=sys.stderr)
        return 64

    t0 = time.monotonic()

    with pdfplumber.open(str(input_pdf)) as pdf:
        pages: list[dict[str, Any]] = []

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            # Approximate blocks from words grouped by line
            words = page.extract_words(keep_blank_chars=False, use_text_flow=True)
            blocks: list[dict[str, Any]] = []
            order = 0

            # Group words into lines by top coordinate
            lines: list[list[dict[str, Any]]] = []
            for w in words:
                placed = False
                for line in lines:
                    if abs(line[0]["top"] - w["top"]) < 3:
                        line.append(w)
                        placed = True
                        break
                if not placed:
                    lines.append([w])

            # Sort lines by top, words in line by x0
            lines.sort(key=lambda ln: ln[0]["top"])
            for line in lines:
                line.sort(key=lambda w: w["x0"])
                content = " ".join(w["text"] for w in line).strip()
                if not content:
                    continue

                x0 = min(w["x0"] for w in line)
                top = min(w["top"] for w in line)
                x1 = max(w["x1"] for w in line)
                bottom = max(w["bottom"] for w in line)

                btype = "paragraph"
                if i == 0 and order == 0 and len(content) < 30:
                    btype = "heading"

                block: dict[str, Any] = {
                    "id": f"p{i + 1}-b{order}",
                    "type": btype,
                    "bbox": [round(x0, 1), round(top, 1), round(x1, 1), round(bottom, 1)],
                    "content": content,
                    "reading_order": order,
                }
                if btype == "heading":
                    block["level"] = 1
                blocks.append(block)
                order += 1

            # Extract tables
            tables: list[dict[str, Any]] = []
            found_tables = page.find_tables()
            for t_idx, tbl in enumerate(found_tables):
                rows = tbl.extract()
                if not rows:
                    continue
                bbox = tbl.bbox
                tables.append({
                    "id": f"p{i + 1}-t{t_idx}",
                    "bbox": [round(bbox[0], 1), round(bbox[1], 1), round(bbox[2], 1), round(bbox[3], 1)],
                    "rows": [[str(c) if c is not None else "" for c in row] for row in rows],
                    "headers": [],
                })

            pages.append({
                "page_number": i + 1,
                "width": page.width,
                "height": page.height,
                "text": text.strip(),
                "blocks": blocks,
                "tables": tables,
            })

        meta = pdf.metadata or {}
        wall_ms_self = (time.monotonic() - t0) * 1000

        result: dict[str, Any] = {
            "schema_version": "1.0.0",
            "metadata": {
                "title": meta.get("Title") or None,
                "author": meta.get("Author") or None,
                "subject": meta.get("Subject") or None,
                "keywords": None,
                "creator": meta.get("Creator") or None,
                "producer": meta.get("Producer") or None,
                "page_count": len(pdf.pages),
                "ocr_used": False,
            },
            "pages": pages,
        }

        result_path = output_dir / "result.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        meta_out: dict[str, Any] = {
            "library": {
                "name": "pdfplumber",
                "version": pdfplumber.__version__,
                "language": "python",
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
    p = argparse.ArgumentParser(prog="python-pdfplumber")
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
        except Exception as exc:
            print(f"extract failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 65
    return 2


if __name__ == "__main__":
    sys.exit(main())
