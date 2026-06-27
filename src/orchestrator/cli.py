"""Orchestrator CLI entry point.

Provides ``orchestrator`` console-script and ``python -m orchestrator`` commands.

Commands:
    run               Run benchmark with all/specified adapters on all/specified fixtures.
    validate-corpus   Validate corpus/manifest.json vs fixtures on disk.
    lint-adapter      Static check that an adapter conforms to the contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click

from orchestrator.models import AdapterEntry, FixtureEntry, RunResult, ScoreResult

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
_LINT_SCRIPT: Path = _REPO_ROOT / "scripts" / "lint_adapter.py"
_SCHEMA_PATH: Path = _REPO_ROOT / "contract" / "result-schema.json"


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
            from orchestrator.models import ScoreResult
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
            except json.JSONDecodeError as e:
                errors.append(f"{fx.id}: expected.json invalid JSON: {e}")

    # Check for fixture dirs on disk not in manifest
    fixtures_dir = corpus_dir / "fixtures"
    if fixtures_dir.exists():
        manifest_ids = {fx.id for fx in fixtures}
        on_disk = {
            d.name for d in fixtures_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        }
        orphaned = on_disk - manifest_ids
        for name in sorted(orphaned):
            errors.append(f"{name}: fixture directory exists but not in manifest")

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

    By default --check-command and --check-help are enabled, matching the
    behavior of ``make lint-adapter`` (scripts/lint-adapter.sh / .ps1).
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


def main() -> None:
    """Entry point for console-script."""
    cli()


if __name__ == "__main__":
    main()
