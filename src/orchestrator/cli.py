"""Orchestrator CLI entry point.

Provides ``orchestrator`` console-script and ``python -m orchestrator`` commands.

Commands:
    run               Run benchmark with all/specified adapters on all/specified fixtures.
    validate-corpus   Validate corpus/manifest.json vs fixtures on disk.
    lint-adapter      Static check that an adapter conforms to the contract.
    add-fixture       Create a new fixture from a PDF file.
    update-fixture    Regenerate expected.json for an existing fixture using a different adapter.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import click

from orchestrator.models import AdapterEntry, FixtureEntry, RunResult, ScoreResult

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
_LINT_SCRIPT: Path = _REPO_ROOT / "scripts" / "lint_adapter.py"
_SCHEMA_PATH: Path = _REPO_ROOT / "contract" / "result-schema.json"
_META_SCHEMA_PATH: Path = _REPO_ROOT / "corpus" / "fixture-meta.schema.json"
_CONFIG_SCHEMA_PATH: Path = _REPO_ROOT / "corpus" / "add-fixture-config.schema.json"
_MANIFEST_SCHEMA_PATH: Path = _REPO_ROOT / "corpus" / "manifest.schema.json"


@click.group()
@click.version_option()
def cli() -> None:
    """eval-pdf-extract orchestrator."""


@cli.command()
@click.option("--corpus", default="corpus/", show_default=True, help="Path to corpus directory.")
@click.option(
    "--adapters",
    default="all",
    show_default=True,
    help="Comma-separated adapter ids or 'all'.",
)
@click.option("--fixture-glob", default=None, help="Glob pattern to filter fixtures.")
@click.option("--workers", default=4, show_default=True, type=int, help="Number of parallel workers.")
@click.option("--results-dir", default="results/", show_default=True, help="Output directory for results.")
@click.option("--run-id", default=None, help="Custom run id. Default: timestamp-based.")
def run(
    corpus: str,
    adapters: str,
    fixture_glob: str | None,
    workers: int,
    results_dir: str,
    run_id: str | None,
) -> None:
    """Run benchmark with adapters on fixtures."""
    from orchestrator.loader import (
        filter_adapters,
        filter_fixtures,
        load_json,
        load_manifest,
        load_registry,
    )
    from orchestrator.report import generate_summary
    from orchestrator.runner import run_one
    from orchestrator.scorer import score
    from orchestrator.store import (
        finalize_run_json,
        init_run_dir,
        write_run_json,
        write_score_json,
        write_scores_csv,
        write_scores_db,
        write_timings,
    )

    corpus_dir = Path(corpus).resolve()
    registry_path = corpus_dir.parent / "adapters" / "registry.json"
    manifest_path = corpus_dir / "manifest.json"
    schema_path = _SCHEMA_PATH
    results_root = Path(results_dir).resolve()

    # Load registry and manifest
    if not registry_path.exists():
        click.echo(f"ERROR: registry not found at {registry_path}", err=True)
        sys.exit(1)
    if not manifest_path.exists():
        click.echo(f"ERROR: manifest not found at {manifest_path}", err=True)
        sys.exit(1)

    all_adapters = load_registry(registry_path)
    all_fixtures = load_manifest(manifest_path)

    selected_adapters = filter_adapters(all_adapters, adapters)
    selected_fixtures = filter_fixtures(all_fixtures, fixture_glob)

    if not selected_adapters:
        click.echo(f"ERROR: no adapters matched '{adapters}'", err=True)
        sys.exit(1)
    if not selected_fixtures:
        click.echo(f"ERROR: no fixtures matched glob '{fixture_glob}'", err=True)
        sys.exit(1)

    # Generate run id
    if run_id is None:
        run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}"

    run_config = {
        "corpus": str(corpus_dir),
        "adapters": [a.id for a in selected_adapters],
        "fixture_glob": fixture_glob,
        "workers": workers,
    }

    run_dir = init_run_dir(results_root, run_id)
    write_run_json(run_dir, run_id, run_config)

    total_pairs = len(selected_adapters) * len(selected_fixtures)
    click.echo(
        f"Run {run_id}: {len(selected_adapters)} adapters x "
        f"{len(selected_fixtures)} fixtures = {total_pairs} pairs",
        err=True,
    )

    all_scores: list[ScoreResult] = []
    completed = 0
    failed = 0

    def _run_pair(
        adapter: AdapterEntry, fixture: FixtureEntry
    ) -> tuple[RunResult, ScoreResult]:
        """Run a single adapter-fixture pair and return (run_result, score_result)."""
        fixture_dir = corpus_dir / "fixtures" / fixture.id
        expected = load_json(fixture_dir / "expected.json")
        if expected is None:
            click.echo(
                f"  WARN: no expected.json for fixture {fixture.id}, skipping scoring",
                err=True,
            )

        rr = run_one(adapter, fixture, corpus_dir, run_dir, schema_path)
        write_timings(rr)

        if expected is not None:
            sr = score(rr, expected, fixture.category)
        else:
            sr = ScoreResult(
                adapter_id=adapter.id,
                fixture_id=fixture.id,
                fixture_category=fixture.category,
                metrics={},
                skipped_metrics=[],
            )
        write_score_json(run_dir, sr)
        return rr, sr

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_run_pair, a, f): (a, f)
            for a in selected_adapters
            for f in selected_fixtures
        }
        for future in as_completed(future_map):
            adapter, fixture = future_map[future]
            pair_label = f"{adapter.id} / {fixture.id}"
            try:
                _rr, sr = future.result()
                all_scores.append(sr)
                if sr.metrics.get("success"):
                    completed += 1
                else:
                    failed += 1
                status = "OK" if sr.metrics.get("success") else "FAIL"
                click.echo(f"  [{status}] {pair_label}", err=True)
            except Exception as e:
                failed += 1
                click.echo(
                    f"  [ERROR] {pair_label}: {type(e).__name__}: {e}",
                    err=True,
                )

    # Write aggregate outputs
    write_scores_csv(run_dir, all_scores)
    write_scores_db(run_dir, all_scores)
    generate_summary(all_scores, run_dir)
    finalize_run_json(run_dir, run_id, run_config, total_pairs, completed, failed)

    click.echo(
        f"\nDone: {completed}/{total_pairs} succeeded, {failed} failed. "
        f"Results in {run_dir}",
        err=True,
    )


@cli.command("validate-corpus")
@click.option("--corpus", default="corpus/", show_default=True, help="Path to corpus directory.")
def validate_corpus(corpus: str) -> None:
    """Validate corpus/manifest.json vs fixtures on disk."""
    from orchestrator.loader import compute_sha256, load_manifest

    corpus_dir = Path(corpus).resolve()
    manifest_path = corpus_dir / "manifest.json"

    if not manifest_path.exists():
        click.echo(f"ERROR: manifest not found at {manifest_path}", err=True)
        sys.exit(1)

    fixtures = load_manifest(manifest_path)
    if not fixtures:
        click.echo("WARN: manifest has no fixtures", err=True)

    errors: list[str] = []
    checked = 0

    for fx in fixtures:
        checked += 1
        fx_dir = corpus_dir / "fixtures" / fx.id
        input_pdf = fx_dir / "input.pdf"
        expected_json = fx_dir / "expected.json"
        meta_json = fx_dir / "meta.json"

        # Check input.pdf exists
        if not input_pdf.exists():
            errors.append(f"{fx.id}: input.pdf not found at {input_pdf}")
            continue

        # Verify sha256
        actual_sha = compute_sha256(input_pdf)
        if actual_sha != fx.sha256:
            errors.append(
                f"{fx.id}: sha256 mismatch (manifest={fx.sha256[:16]}... "
                f"actual={actual_sha[:16]}...)"
            )

        # Check expected.json exists
        if not expected_json.exists():
            errors.append(f"{fx.id}: expected.json not found")

        # Check meta.json exists
        if not meta_json.exists():
            errors.append(f"{fx.id}: meta.json not found")

        # Check expected_page_count if expected.json exists
        if expected_json.exists():
            try:
                with expected_json.open("r", encoding="utf-8") as f:
                    exp = json.load(f)
                exp_pages = len(exp.get("pages", []))
                exp_meta = exp.get("metadata", {})
                exp_pc = exp_meta.get("page_count")
                if exp_pc is not None and exp_pc != fx.expected_page_count:
                    errors.append(
                        f"{fx.id}: expected_page_count mismatch "
                        f"(manifest={fx.expected_page_count}, "
                        f"expected.json={exp_pc})"
                    )
                if exp_pc is not None and exp_pc != exp_pages:
                    errors.append(
                        f"{fx.id}: page_count={exp_pc} but "
                        f"pages array has {exp_pages} entries"
                    )
                # Check pages array length vs manifest only when
                # metadata.page_count is absent (otherwise check 1 covers it)
                elif exp_pages != fx.expected_page_count:
                    errors.append(
                        f"{fx.id}: pages array has {exp_pages} entries "
                        f"but manifest expected_page_count={fx.expected_page_count}"
                    )
            except json.JSONDecodeError as e:
                errors.append(f"{fx.id}: expected.json invalid JSON: {e}")

    # Check for fixture dirs on disk not in manifest
    fixtures_dir = corpus_dir / "fixtures"
    orphans: list[str] = []
    if fixtures_dir.exists():
        manifest_ids = {fx.id for fx in fixtures}
        on_disk = {
            d.name for d in fixtures_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        }
        for name in sorted(on_disk - manifest_ids):
            # Check if dir is empty (only .gitkeep or truly empty)
            dir_path = fixtures_dir / name
            real_files = [
                f for f in dir_path.iterdir()
                if f.name != ".gitkeep" and not f.name.startswith(".")
            ]
            if not real_files:
                orphans.append(name)
            else:
                errors.append(f"{name}: fixture directory has files but not in manifest")

    if orphans:
        click.echo(
            f"INFO: {len(orphans)} empty placeholder dir(s) not in manifest "
            f"(harmless): {', '.join(orphans)}",
            err=True,
        )

    if errors:
        click.echo(f"FAIL: {len(errors)} error(s) in {checked} fixture(s):", err=True)
        for err in errors:
            click.echo(f"  {err}", err=True)
        sys.exit(1)

    click.echo(f"OK: {checked} fixture(s) validated, no errors.", err=True)


@cli.command("lint-adapter")
@click.argument("adapter_id", required=False)
@click.option("--check-command", is_flag=True, help="Also verify <cmd> is in PATH.")
@click.option("--check-help", is_flag=True, help="Also run <cmd> --help (implies --check-command).")
def lint_adapter(adapter_id: str | None, check_command: bool, check_help: bool) -> None:
    """Static check that an adapter conforms to the contract.

    Pass --check-command to verify the adapter's command is in PATH.
    Pass --check-help to also run <cmd> --help (implies --check-command).
    """
    if not _LINT_SCRIPT.exists():
        click.echo(
            f"ERROR: lint_adapter.py not found at {_LINT_SCRIPT}\n"
            "Hint: orchestrator must be installed in editable mode (uv sync / pip install -e .).",
            err=True,
        )
        sys.exit(1)
    args: list[str] = [sys.executable, str(_LINT_SCRIPT)]
    if adapter_id:
        args.append(adapter_id)
    if check_command or check_help:
        args.append("--check-command")
    if check_help:
        args.append("--check-help")
    result = subprocess.run(args, check=False)
    sys.exit(result.returncode)


_VALID_CATEGORIES = (
    "plain_text", "multi_column", "table", "form",
    "scanned", "multilang", "edge",
)

_CATEGORY_NUMBERS: dict[str, str] = {
    "plain_text": "01",
    "multi_column": "02",
    "table": "03",
    "form": "04",
    "scanned": "05",
    "multilang": "06",
    "edge": "07",
}


def _validate_json(data: dict[str, Any], schema_path: Path) -> list[str]:
    """Validate data against a JSON schema. Returns list of error messages (empty = valid)."""
    if not schema_path.exists():
        return [f"schema file not found: {schema_path}"]
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [f"{'.'.join(str(p) for p in e.path) or 'root'}: {e.message}" for e in errors]


@cli.command("add-fixture")
@click.option("--input", "input_pdf", type=Path, default=None,
              help="Path to the PDF file. Overrides config.")
@click.option("--category", default=None,
              type=click.Choice(_VALID_CATEGORIES),
              help="Fixture category. Overrides config.")
@click.option("--slug", default=None,
              help="Short slug for fixture id. Overrides config.")
@click.option("--title", default=None, help="Title of the source document. Overrides config.")
@click.option("--license", "license_str", default=None,
              help="License of the source document. Overrides config.")
@click.option("--corpus", default=None,
              help="Path to corpus directory. Overrides config.")
@click.option("--author", default=None, help="Ground truth author name. Overrides config.")
@click.option("--difficulty", default=None,
              type=click.Choice(["easy", "medium", "hard"]),
              help="Difficulty level. Overrides config.")
@click.option("--tags", default=None, help="Comma-separated tags. Overrides config.")
@click.option("--adapter", default=None,
              help="Adapter id to use for generating expected.json (e.g. python-pymupdf). "
                   "Overrides config. Defaults to python-pymupdf.")
@click.option("--config", "config_path", default=None, type=Path,
              help="Path to YAML config file for add-fixture defaults.")
def add_fixture(
    input_pdf: Path | None,
    category: str | None,
    slug: str | None,
    title: str | None,
    license_str: str | None,
    corpus: str | None,
    author: str | None,
    difficulty: str | None,
    tags: str | None,
    adapter: str | None,
    config_path: Path | None,
) -> None:
    """Create a new fixture from a PDF file.

    Reads defaults from a YAML config file (--config), with CLI args overriding.
    Uses an adapter subprocess to generate expected.json (not hardcoded to PyMuPDF).

    Config file format (e.g. corpus/add-fixture.yaml):
    \b
        input: path/to/resume.pdf
        category: plain_text
        slug: resume
        title: "Sample Resume"
        license: CC0-1.0
        author: your-name
        difficulty: easy
        tags: english,single_column
        adapter: python-pymupdf
        corpus: corpus/
    """
    import yaml

    # Load config file if provided, else empty
    cfg: dict[str, Any] = {}
    if config_path is not None:
        if not config_path.exists():
            click.echo(f"ERROR: config file not found: {config_path}", err=True)
            sys.exit(1)
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        # Validate config against schema
        cfg_errors = _validate_json(cfg, _CONFIG_SCHEMA_PATH)
        if cfg_errors:
            click.echo("ERROR: config file validation failed:", err=True)
            for e in cfg_errors:
                click.echo(f"  {e}", err=True)
            sys.exit(1)

    # Merge: CLI args override config file values
    input_pdf = Path(input_pdf) if input_pdf else Path(cfg["input"]) if "input" in cfg else None
    category = category or cfg.get("category")
    slug = slug or cfg.get("slug")
    title = title or cfg.get("title", "")
    license_str = license_str or cfg.get("license", "unknown")
    corpus = corpus or cfg.get("corpus", "corpus/")
    author = author or cfg.get("author", "")
    difficulty = difficulty or cfg.get("difficulty", "easy")
    tags = tags or cfg.get("tags", "")
    adapter_id = adapter or cfg.get("adapter", "python-pymupdf")

    # Validate required params
    missing = []
    if input_pdf is None:
        missing.append("input")
    if category is None:
        missing.append("category")
    if slug is None:
        missing.append("slug")
    if missing:
        click.echo(
            f"ERROR: missing required parameter(s): {', '.join(missing)}\n"
            "Provide via CLI args or config file.",
            err=True,
        )
        sys.exit(1)

    from orchestrator.loader import compute_sha256, load_registry

    corpus_dir = Path(corpus).resolve()
    assert input_pdf is not None  # checked above
    input_pdf = input_pdf.resolve()

    if not input_pdf.exists():
        click.echo(f"ERROR: input PDF not found: {input_pdf}", err=True)
        sys.exit(1)

    fixtures_dir = corpus_dir / "fixtures"
    if not fixtures_dir.exists():
        click.echo(f"ERROR: fixtures dir not found: {fixtures_dir}", err=True)
        sys.exit(1)

    # Resolve adapter (version-less → latest)
    registry_path = corpus_dir.parent / "adapters" / "registry.json"
    all_adapters = load_registry(registry_path)
    from orchestrator.loader import filter_adapters

    matched = filter_adapters(all_adapters, adapter_id)
    if not matched:
        click.echo(f"ERROR: adapter '{adapter_id}' not found in registry", err=True)
        sys.exit(1)
    adapter_entry = matched[0]

    # Determine fixture id and directory
    num = _CATEGORY_NUMBERS.get(category or "", "00")
    fixture_id = f"{num}_{category}__{slug}"
    fixture_dir = fixtures_dir / fixture_id

    if fixture_dir.exists():
        existing_files = [
            f for f in fixture_dir.iterdir()
            if f.name != ".gitkeep" and not f.name.startswith(".")
        ]
        if existing_files:
            click.echo(
                f"ERROR: fixture directory already exists and is not empty: {fixture_dir}",
                err=True,
            )
            sys.exit(1)

    fixture_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy PDF as input.pdf
    import shutil
    dest_pdf = fixture_dir / "input.pdf"
    shutil.copy2(str(input_pdf), str(dest_pdf))

    # 2. Compute sha256
    sha256 = compute_sha256(dest_pdf)
    click.echo(f"  sha256: {sha256}", err=True)

    # 3. Generate expected.json by running the adapter
    click.echo(f"  extracting text with adapter '{adapter_entry.id}'...", err=True)
    expected = _generate_expected_via_adapter(dest_pdf, fixture_dir, adapter_entry, _SCHEMA_PATH)
    if expected is None:
        click.echo(
            f"ERROR: adapter '{adapter_entry.id}' failed to produce valid result.json",
            err=True,
        )
        sys.exit(1)
    page_count = len(expected.get("pages", []))
    click.echo(f"  pages: {page_count}", err=True)

    (fixture_dir / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 4. Write meta.json (validated against fixture-meta.schema.json)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    import datetime
    today = datetime.date.today().isoformat()
    meta = {
        "fixture_id": fixture_id,
        "category": category,
        "tags": tag_list,
        "difficulty": difficulty,
        "expected_page_count": page_count,
        "input_pdf_sha256": sha256,
        "source": {
            "title": title or input_pdf.stem,
            "url": "",
            "license": license_str,
            "note": "",
        },
        "ground_truth_authors": [author] if author else [],
        "revisions": [
            {
                "date": today,
                "author": author or "unknown",
                "note": f"initial version, extracted with {adapter_entry.id}",
            }
        ],
    }
    meta_errors = _validate_json(meta, _META_SCHEMA_PATH)
    if meta_errors:
        click.echo("ERROR: meta.json schema validation failed:", err=True)
        for e in meta_errors:
            click.echo(f"  {e}", err=True)
        sys.exit(1)
    (fixture_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 5. Update manifest.json
    manifest_path = corpus_dir / "manifest.json"
    manifest: dict[str, Any] = {"$schema": "./manifest.schema.json"}
    if manifest_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    fixtures = manifest.get("fixtures", [])
    fixtures = [f for f in fixtures if f.get("id") != fixture_id]
    fixtures.append({
        "id": fixture_id,
        "path": f"fixtures/{fixture_id}/input.pdf",
        "category": category,
        "tags": tag_list,
        "difficulty": difficulty,
        "expected_page_count": page_count,
        "sha256": sha256,
        "source": {
            "title": title or input_pdf.stem,
            "license": license_str,
        },
        "notes": "",
    })
    manifest["fixtures"] = fixtures
    manifest_errors = _validate_json(manifest, _MANIFEST_SCHEMA_PATH)
    if manifest_errors:
        click.echo("ERROR: manifest.json schema validation failed:", err=True)
        for e in manifest_errors:
            click.echo(f"  {e}", err=True)
        sys.exit(1)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    click.echo(
        f"\nDone: fixture '{fixture_id}' created at {fixture_dir}",
        err=True,
    )
    click.echo("  Run 'make validate-corpus' to verify.", err=True)


@cli.command("update-fixture")
@click.option("--fixture", "fixture_id", required=True,
              help="Fixture id, e.g. '01_plain_text__resume'.")
@click.option("--adapter", default="python-pymupdf",
              help="Adapter id to use for regenerating expected.json. "
                   "Supports version-less matching. Defaults to python-pymupdf.")
@click.option("--corpus", default="corpus/", show_default=True,
              help="Path to corpus directory.")
@click.option("--note", default="",
              help="Revision note for meta.json. Defaults to auto-generated.")
def update_fixture(
    fixture_id: str,
    adapter: str,
    corpus: str,
    note: str,
) -> None:
    """Regenerate expected.json for an existing fixture using a different adapter.

    Does NOT touch input.pdf or sha256. Only:
    1. Re-runs the specified adapter on the existing input.pdf.
    2. Overwrites expected.json with the new result.
    3. Appends a revision entry to meta.json.
    4. Updates manifest.json entry (page_count may change).
    """
    from orchestrator.loader import load_registry

    corpus_dir = Path(corpus).resolve()
    fixture_dir = corpus_dir / "fixtures" / fixture_id
    input_pdf = fixture_dir / "input.pdf"

    if not input_pdf.exists():
        click.echo(f"ERROR: fixture not found: {fixture_dir}", err=True)
        sys.exit(1)

    # Resolve adapter
    registry_path = corpus_dir.parent / "adapters" / "registry.json"
    all_adapters = load_registry(registry_path)
    from orchestrator.loader import filter_adapters

    matched = filter_adapters(all_adapters, adapter)
    if not matched:
        click.echo(f"ERROR: adapter '{adapter}' not found in registry", err=True)
        sys.exit(1)
    adapter_entry = matched[0]

    # 1. Regenerate expected.json
    click.echo(f"  extracting text with adapter '{adapter_entry.id}'...", err=True)
    expected = _generate_expected_via_adapter(input_pdf, fixture_dir, adapter_entry, _SCHEMA_PATH)
    if expected is None:
        click.echo(
            f"ERROR: adapter '{adapter_entry.id}' failed to produce valid result.json",
            err=True,
        )
        sys.exit(1)
    page_count = len(expected.get("pages", []))
    click.echo(f"  pages: {page_count}", err=True)

    (fixture_dir / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 2. Append revision to meta.json
    import datetime
    today = datetime.date.today().isoformat()
    meta_path = fixture_dir / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

    revisions = meta.get("revisions", [])
    revisions.append({
        "date": today,
        "author": adapter_entry.id,
        "note": note or f"regenerated expected.json with {adapter_entry.id}",
    })
    meta["revisions"] = revisions
    meta["expected_page_count"] = page_count

    meta_errors = _validate_json(meta, _META_SCHEMA_PATH)
    if meta_errors:
        click.echo("ERROR: meta.json schema validation failed:", err=True)
        for e in meta_errors:
            click.echo(f"  {e}", err=True)
        sys.exit(1)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 3. Update manifest.json entry
    manifest_path = corpus_dir / "manifest.json"
    manifest: dict[str, Any] = {"$schema": "./manifest.schema.json"}
    if manifest_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    fixtures = manifest.get("fixtures", [])
    for f in fixtures:
        if f.get("id") == fixture_id:
            f["expected_page_count"] = page_count
            break

    manifest["fixtures"] = fixtures
    manifest_errors = _validate_json(manifest, _MANIFEST_SCHEMA_PATH)
    if manifest_errors:
        click.echo("ERROR: manifest.json schema validation failed:", err=True)
        for e in manifest_errors:
            click.echo(f"  {e}", err=True)
        sys.exit(1)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    click.echo(
        f"\nDone: fixture '{fixture_id}' updated (expected.json regenerated with {adapter_entry.id})",
        err=True,
    )
    click.echo("  Run 'make validate-corpus' to verify.", err=True)


def _generate_expected_via_adapter(
    pdf_path: Path,
    fixture_dir: Path,
    adapter: AdapterEntry,
    schema_path: Path,
) -> dict[str, Any] | None:
    """Run an adapter on a PDF and return its result.json as a dict.

    Uses a temp output dir, validates against schema, returns None on failure.
    """
    import tempfile

    from orchestrator.runner import validate_result_schema

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_output = Path(tmpdir)
        cfg = {"ocr": {"enabled": True}}
        cmd = [
            adapter.command,
            "extract",
            "--input", str(pdf_path),
            "--output-dir", str(tmp_output),
            "--config", json.dumps(cfg),
            "--timeout", str(adapter.timeout_seconds),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=adapter.timeout_seconds + 10)
        if result.returncode != 0:
            click.echo(
                f"  adapter stderr: {result.stderr[:500]}",
                err=True,
            )
            return None

        result_path = tmp_output / "result.json"
        if not result_path.exists():
            click.echo("  adapter did not produce result.json", err=True)
            return None

        data = json.loads(result_path.read_text(encoding="utf-8"))
        if not validate_result_schema(data, schema_path):
            click.echo("  adapter result.json failed schema validation", err=True)
            return None

        return data  # type: ignore[no-any-return]


def main() -> None:
    """Entry point for console-script."""
    cli()


if __name__ == "__main__":
    main()
