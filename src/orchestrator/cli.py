"""Orchestrator CLI entry point.

Provides ``orchestrator`` console-script and ``python -m orchestrator`` commands.

Commands:
    run               Run benchmark with all/specified adapters on all/specified fixtures.
    validate-corpus   Validate corpus/manifest.json vs fixtures on disk.
    lint-adapter      Static check that an adapter conforms to the contract.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
_LINT_SCRIPT: Path = _REPO_ROOT / "scripts" / "lint_adapter.py"


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
def run(
    corpus: str,
    adapters: str,
    fixture_glob: str | None,
    workers: int,
) -> None:
    """Run benchmark with adapters on fixtures."""
    click.echo(
        f"orchestrator run: corpus={corpus} adapters={adapters} "
        f"fixture_glob={fixture_glob} workers={workers}",
        err=True,
    )
    click.echo("ERROR: orchestrator runner not yet implemented.", err=True)
    sys.exit(1)


@cli.command("validate-corpus")
@click.option("--corpus", default="corpus/", show_default=True, help="Path to corpus directory.")
def validate_corpus(corpus: str) -> None:
    """Validate corpus/manifest.json vs fixtures on disk."""
    click.echo(f"orchestrator validate-corpus: corpus={corpus}", err=True)
    click.echo("ERROR: corpus validation not yet implemented.", err=True)
    sys.exit(1)


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
    args.append("--check-command")
    args.append("--check-help")
    result = subprocess.run(args, check=False)
    sys.exit(result.returncode)


def main() -> None:
    """Entry point for console-script."""
    cli()


if __name__ == "__main__":
    main()
