"""PyMuPDF adapter for eval-pdf-extract.

CLI entry point implementing the adapter protocol (contract/adapter-protocol.md).

Known gaps in this reference implementation:
- timeout: accepted but not enforced; the orchestrator's hard timeout
  (timeout + 5s) is the backstop. Self-termination is not implemented.
- config: accepted but ignored; options like ocr.enabled, max_pages
  have no effect. All pages are always extracted without OCR.
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
    import pymupdf

    if not input_pdf.exists():
        print(f"input not found: {input_pdf}", file=sys.stderr)
        return 64

    t0 = time.monotonic()
    with pymupdf.open(str(input_pdf)) as doc:

        pages: list[dict[str, Any]] = []
        for i, page in enumerate(doc):
            blocks_raw = page.get_text("dict")["blocks"]
            blocks: list[dict[str, Any]] = []
            text_parts: list[str] = []
            order = 0

            for b in blocks_raw:
                if b["type"] != 0:
                    continue
                bbox = b["bbox"]
                content = "".join(
                    span["text"] for line in b["lines"] for span in line["spans"]
                ).strip()
                if not content:
                    continue

                btype = "paragraph"
                if i == 0 and order == 0 and len(content) < 30:
                    btype = "heading"

                block: dict[str, Any] = {
                    "id": f"p{i + 1}-b{order}",
                    "type": btype,
                    "bbox": [
                        round(bbox[0], 1),
                        round(bbox[1], 1),
                        round(bbox[2], 1),
                        round(bbox[3], 1),
                    ],
                    "content": content,
                    "reading_order": order,
                }
                if btype == "heading":
                    block["level"] = 1
                blocks.append(block)
                text_parts.append(content)
                order += 1

            pages.append(
                {
                    "page_number": i + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "text": "\n".join(text_parts),
                    "blocks": blocks,
                    "tables": [],
                }
            )

        meta = doc.metadata or {}
        wall_ms_self = (time.monotonic() - t0) * 1000

        result: dict[str, Any] = {
            "schema_version": "1.0.0",
            "metadata": {
                "title": meta.get("title") or None,
                "author": meta.get("author") or None,
                "subject": meta.get("subject") or None,
                "keywords": None,
                "creator": meta.get("creator") or None,
                "producer": meta.get("producer") or None,
                "page_count": doc.page_count,
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
                "name": "PyMuPDF",
                "version": pymupdf.__version__,
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
    p = argparse.ArgumentParser(prog="python-pymupdf")
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
