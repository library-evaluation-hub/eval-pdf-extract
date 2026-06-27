"""Loaders for registry.json, manifest.json, and fixture data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from orchestrator.models import AdapterEntry, FixtureEntry


def load_registry(registry_path: Path) -> list[AdapterEntry]:
    """Load adapters/registry.json and return list of AdapterEntry."""
    with registry_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    entries: list[AdapterEntry] = []
    for raw in data.get("adapters", []):
        entries.append(
            AdapterEntry(
                id=raw["id"],
                command=raw["command"],
                language=raw["language"],
                timeout_seconds=raw.get("timeout_seconds", 60),
                supports_ocr=raw.get("supports_ocr", False),
                disabled=raw.get("disabled", False),
            )
        )
    return entries


def load_manifest(manifest_path: Path) -> list[FixtureEntry]:
    """Load corpus/manifest.json and return list of FixtureEntry."""
    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    entries: list[FixtureEntry] = []
    for raw in data.get("fixtures", []):
        entries.append(
            FixtureEntry(
                id=raw["id"],
                path=raw["path"],
                category=raw["category"],
                expected_page_count=raw["expected_page_count"],
                sha256=raw["sha256"],
                tags=raw.get("tags", []),
                difficulty=raw.get("difficulty"),
            )
        )
    return entries


def load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON file, returning None if file doesn't exist or is invalid."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string like '1.24.0' into (1, 24, 0) for comparison."""
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def filter_adapters(
    all_adapters: list[AdapterEntry], selection: str
) -> list[AdapterEntry]:
    """Filter adapters by 'all' or comma-separated ids. Skips disabled.

    Each selection id can be:
    - Full id with version: 'python-pymupdf@1.24.0' → exact match
    - Name without version: 'python-pymupdf' → matches latest version
    """
    active = [a for a in all_adapters if not a.disabled]
    if selection == "all":
        return active

    selections = list(dict.fromkeys(s.strip() for s in selection.split(",") if s.strip()))
    result: list[AdapterEntry] = []
    seen_ids: set[str] = set()

    for sel in selections:
        if "@" in sel:
            # Exact id match
            for a in active:
                if a.id == sel and a.id not in seen_ids:
                    result.append(a)
                    seen_ids.add(a.id)
        else:
            # Version-less: match latest version of this name
            candidates = [a for a in active if a.id.split("@")[0] == sel]
            if candidates:
                latest = max(candidates, key=lambda a: _parse_version(a.id.split("@")[1]))
                if latest.id not in seen_ids:
                    result.append(latest)
                    seen_ids.add(latest.id)

    return result


def filter_fixtures(
    all_fixtures: list[FixtureEntry], glob_pattern: str | None
) -> list[FixtureEntry]:
    """Filter fixtures by glob pattern on fixture id. None = all."""
    if glob_pattern is None:
        return all_fixtures
    import fnmatch

    return [f for f in all_fixtures if fnmatch.fnmatch(f.id, glob_pattern)]
