"""Data access layer for WebUI backend.

Reads from results/, scores.db, adapters/registry.json, corpus/manifest.json.
All functions are read-only.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from orchestrator.loader import load_manifest, load_registry
from orchestrator.models import ALL_METRIC_IDS, METRIC_CATEGORIES


def _project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).resolve().parents[3]


def _results_root() -> Path:
    """Return the results/ directory."""
    return _project_root() / "results"


def _registry_path() -> Path:
    return _project_root() / "adapters" / "registry.json"


def _manifest_path() -> Path:
    return _project_root() / "corpus" / "manifest.json"


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


def list_runs() -> list[dict[str, Any]]:
    """List all runs in results/, sorted by started_at descending."""
    results_root = _results_root()
    if not results_root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for run_dir in results_root.iterdir():
        if not run_dir.is_dir():
            continue
        run_json = run_dir / "run.json"
        if not run_json.exists():
            continue
        try:
            data = json.loads(run_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        data["run_id"] = data.get("run_id", run_dir.name)
        data.setdefault("total_pairs", 0)
        data.setdefault("completed", 0)
        data.setdefault("failed", 0)
        data.setdefault("started_at", "")
        data.setdefault("completed_at", "")
        runs.append(data)
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return runs


def get_run(run_id: str) -> dict[str, Any] | None:
    """Get a single run's metadata."""
    run_json = _results_root() / run_id / "run.json"
    if not run_json.exists():
        return None
    try:
        result: dict[str, Any] = json.loads(run_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    result["run_id"] = result.get("run_id", run_id)
    result.setdefault("total_pairs", 0)
    result.setdefault("completed", 0)
    result.setdefault("failed", 0)
    result.setdefault("started_at", "")
    result.setdefault("completed_at", "")
    return result


def get_run_scores(run_id: str) -> list[dict[str, Any]]:
    """Get all scores for a run from scores.db."""
    db_path = _results_root() / run_id / "scores.db"
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT adapter_id, fixture_id, fixture_category, metric, value, value_text, skipped "
            "FROM scores ORDER BY adapter_id, fixture_id, metric"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_run_leaderboard(run_id: str) -> list[dict[str, Any]]:
    """Aggregate scores per adapter for a run, suitable for leaderboard display."""
    scores = get_run_scores(run_id)
    if not scores:
        return []

    # Group by adapter_id
    adapters: dict[str, dict[str, Any]] = {}
    for row in scores:
        aid = row["adapter_id"]
        if aid not in adapters:
            adapters[aid] = {
                "adapter_id": aid,
                "metrics": {},
            }
        metric = row["metric"]
        if row["skipped"]:
            continue
        val = row["value"]
        if val is None:
            val = row["value_text"]
        if val is not None:
            adapters[aid]["metrics"].setdefault(metric, []).append(val)

    # Aggregate: mean for numeric metrics, mode for string metrics
    result: list[dict[str, Any]] = []
    for aid, info in adapters.items():
        agg: dict[str, Any] = {"adapter_id": aid}
        for metric_id in ALL_METRIC_IDS:
            vals = info["metrics"].get(metric_id)
            if not vals:
                agg[metric_id] = None
                continue
            category = METRIC_CATEGORIES.get(metric_id, "")
            if category == "robustness" and metric_id == "error_category":
                # Mode for error_category
                from collections import Counter
                agg[metric_id] = Counter(vals).most_common(1)[0][0]
            elif all(isinstance(v, (int, float)) for v in vals):
                agg[metric_id] = round(sum(vals) / len(vals), 4)
            else:
                agg[metric_id] = vals[0]
        result.append(agg)
    return result


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #


def list_adapters() -> list[dict[str, Any]]:
    """List all adapters from registry.json."""
    registry_path = _registry_path()
    if not registry_path.exists():
        return []
    adapters = load_registry(registry_path)
    return [
        {
            "id": a.id,
            "command": a.command,
            "language": a.language,
            "timeout_seconds": a.timeout_seconds,
            "supports_ocr": a.supports_ocr,
            "disabled": a.disabled,
        }
        for a in adapters
    ]


def get_adapter(adapter_id: str) -> dict[str, Any] | None:
    """Get a single adapter's info plus its scores across all runs."""
    adapters = list_adapters()
    info = next((a for a in adapters if a["id"] == adapter_id), None)
    if info is None:
        return None

    # Collect fixture-level scores from all runs
    runs = list_runs()
    fixture_scores: list[dict[str, Any]] = []
    for run in runs:
        run_id = run["run_id"]
        db_path = _results_root() / run_id / "scores.db"
        if not db_path.exists():
            continue
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT fixture_id, fixture_category, metric, value, value_text, skipped "
                "FROM scores WHERE adapter_id = ? ORDER BY fixture_id, metric",
                (adapter_id,),
            ).fetchall()
            # Group by fixture
            fixtures: dict[str, dict[str, Any]] = {}
            for r in rows:
                fid = r["fixture_id"]
                if fid not in fixtures:
                    fixtures[fid] = {
                        "fixture_id": fid,
                        "fixture_category": r["fixture_category"],
                        "run_id": run_id,
                        "metrics": {},
                    }
                metric = r["metric"]
                if r["skipped"]:
                    fixtures[fid]["metrics"][metric] = None
                else:
                    val = r["value"]
                    if val is None:
                        val = r["value_text"]
                    fixtures[fid]["metrics"][metric] = val
            fixture_scores.extend(fixtures.values())
        finally:
            conn.close()

    return {**info, "fixture_scores": fixture_scores}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def list_fixtures() -> list[dict[str, Any]]:
    """List all fixtures from manifest.json."""
    manifest_path = _manifest_path()
    if not manifest_path.exists():
        return []
    fixtures = load_manifest(manifest_path)
    return [
        {
            "id": f.id,
            "path": f.path,
            "category": f.category,
            "expected_page_count": f.expected_page_count,
            "sha256": f.sha256,
            "tags": f.tags,
            "difficulty": f.difficulty,
        }
        for f in fixtures
    ]


def get_fixture(fixture_id: str) -> dict[str, Any] | None:
    """Get a single fixture's info plus its expected.json and adapter results."""
    fixtures = list_fixtures()
    info = next((f for f in fixtures if f["id"] == fixture_id), None)
    if info is None:
        return None

    # Load expected.json
    fixture_dir = _project_root() / "corpus" / "fixtures" / fixture_id
    expected_path = fixture_dir / "expected.json"
    expected: dict[str, Any] | None = None
    if expected_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            expected = json.loads(expected_path.read_text(encoding="utf-8"))

    # Collect adapter results from all runs
    runs = list_runs()
    adapter_results: list[dict[str, Any]] = []
    for run in runs:
        run_id = run["run_id"]
        run_dir = _results_root() / run_id
        # Find all adapter dirs that have this fixture
        if not run_dir.exists():
            continue
        for adapter_dir in run_dir.iterdir():
            if not adapter_dir.is_dir() or adapter_dir.name in (".", ".."):
                continue
            fixture_result_dir = adapter_dir / fixture_id
            if not fixture_result_dir.exists():
                continue
            entry: dict[str, Any] = {
                "run_id": run_id,
                "adapter_id": adapter_dir.name,
                "fixture_id": fixture_id,
            }
            # Load result.json
            result_path = fixture_result_dir / "result.json"
            if result_path.exists():
                try:
                    entry["result"] = json.loads(result_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    entry["result"] = None
            else:
                entry["result"] = None
            # Load score.json
            score_path = fixture_result_dir / "score.json"
            if score_path.exists():
                try:
                    entry["score"] = json.loads(score_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    entry["score"] = None
            else:
                entry["score"] = None
            # Load stderr.log
            stderr_path = fixture_result_dir / "stderr.log"
            if stderr_path.exists():
                with contextlib.suppress(OSError):
                    entry["stderr"] = stderr_path.read_text(encoding="utf-8")
            else:
                entry["stderr"] = ""
            adapter_results.append(entry)

    return {**info, "expected": expected, "adapter_results": adapter_results}


# --------------------------------------------------------------------------- #
# Compare
# --------------------------------------------------------------------------- #


def get_compare_data(
    run_ids: list[str],
    fixture_ids: list[str],
    adapter_ids: list[str],
) -> dict[str, Any] | None:
    """Get comparison data across multiple runs for given fixtures and adapters.

    Returns a dict with:
    - run_ids: list of run IDs that were found
    - fixtures: list of {fixture_id, expected, adapter_results: {key: {run_id, adapter_id, result, score}}}

    The adapter_results key is "run_id/adapter_id" so the frontend can
    distinguish results from different runs.

    Identical adapter+fixture combinations across runs are deduplicated:
    if the result.json content is identical, only the first occurrence is kept.

    Returns None if none of the run_ids exist.
    """
    results_root = _results_root()
    valid_run_ids: list[str] = []
    for rid in run_ids:
        if (results_root / rid / "run.json").exists():
            valid_run_ids.append(rid)
    if not valid_run_ids:
        return None

    result: dict[str, Any] = {"run_ids": valid_run_ids, "fixtures": []}

    for fid in fixture_ids:
        fixture_data: dict[str, Any] = {"fixture_id": fid, "adapter_results": {}}

        # Load expected.json
        fixture_dir = _project_root() / "corpus" / "fixtures" / fid
        expected_path = fixture_dir / "expected.json"
        if expected_path.exists():
            try:
                fixture_data["expected"] = json.loads(
                    expected_path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                fixture_data["expected"] = None
        else:
            fixture_data["expected"] = None

        # Track seen result hashes for dedup: (adapter_id) -> serialized result
        seen_results: dict[str, str] = {}

        for rid in valid_run_ids:
            run_dir = results_root / rid
            for aid in adapter_ids:
                adapter_fixture_dir = run_dir / aid / fid
                result_path = adapter_fixture_dir / "result.json"

                if not result_path.exists():
                    continue

                result_data: Any = None
                try:
                    result_data = json.loads(
                        result_path.read_text(encoding="utf-8")
                    )
                except (json.JSONDecodeError, OSError):
                    result_data = None

                # Dedup: skip if identical result already seen for this adapter
                result_serialized = json.dumps(result_data, sort_keys=True) if result_data else ""
                if aid in seen_results and seen_results[aid] == result_serialized:
                    continue
                seen_results[aid] = result_serialized

                score_data: Any = None
                score_path = adapter_fixture_dir / "score.json"
                if score_path.exists():
                    try:
                        score_data = json.loads(
                            score_path.read_text(encoding="utf-8")
                        )
                    except (json.JSONDecodeError, OSError):
                        score_data = None

                key = f"{rid}/{aid}"
                fixture_data["adapter_results"][key] = {
                    "run_id": rid,
                    "adapter_id": aid,
                    "result": result_data,
                    "score": score_data,
                }

        result["fixtures"].append(fixture_data)

    return result
