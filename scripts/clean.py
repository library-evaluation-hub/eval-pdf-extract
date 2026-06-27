#!/usr/bin/env python3
"""Cross-platform cleanup for eval-pdf-extract.

Equivalent to:
    rm -rf build/ dist/ .pytest_cache/ .mypy_cache/ .ruff_cache/
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf results/*  (keep results/sample/)

Replaces the bash-only idiom in the original Makefile so it works
identically on Windows (PowerShell) and Linux/macOS.
"""
from __future__ import annotations

import contextlib
import shutil
import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

TOP_LEVEL: tuple[str, ...] = (
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    "site",
)

SAMPLE_KEEP: str = "sample"  # results/<this>/ is preserved


def _rmtree_or_unlink(p: Path) -> None:
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    elif p.exists():
        with contextlib.suppress(OSError):
            p.unlink()


def main() -> int:
    removed_top: list[str] = []
    for name in TOP_LEVEL:
        p = ROOT / name
        if p.exists():
            _rmtree_or_unlink(p)
            removed_top.append(name)

    pycache_n = 0
    for d in ROOT.rglob("__pycache__"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            pycache_n += 1

    # .egg-info / .dist-info often under src/.../foo.egg-info/
    egg_n = 0
    for d in ROOT.rglob("*.egg-info"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            egg_n += 1
    for d in ROOT.rglob("*.dist-info"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            egg_n += 1

    results = ROOT / "results"
    results_n = 0
    if results.exists():
        for child in results.iterdir():
            if child.name == SAMPLE_KEEP:
                continue
            _rmtree_or_unlink(child)
            results_n += 1

    print(
        f"clean: top={removed_top or '-'} "
        f"__pycache__={pycache_n} egg-info={egg_n} results/={results_n}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
