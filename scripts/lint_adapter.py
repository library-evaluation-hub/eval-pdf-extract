#!/usr/bin/env python3
"""lint-adapter: validate entries in adapters/registry.json.

Usage:
    uv run python scripts/lint_adapter.py <adapter-id>
    uv run python scripts/lint_adapter.py                   # global checks only
    uv run python scripts/lint_adapter.py --check-command   # also verify <cmd> in PATH
    uv run python scripts/lint_adapter.py --check-help      # also run <cmd> --help (implies --check-command)

Checks:
    [R1] (single)  adapter id exists in registry
    [R2] (single)  adapter id matches '<lang>-<lib>@<version>' pattern
    [G1] (global)  no two non-disabled entries share the same command
    [C1] (--check-command) command is in PATH
    [C2] (--check-help)    command runs '<cmd> --help' with exit 0

Exit codes:
    0  all checks passed
    1  one or more checks failed
    2  invalid usage / IO error

Note: ``python -m orchestrator lint-adapter`` (cli.py) delegates to this
script as its backend. The shell wrappers (lint-adapter.sh / .ps1) also
call this script directly. All three entry points share the same logic.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
REGISTRY: Path = REPO_ROOT / "adapters" / "registry.json"

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*@[0-9][0-9a-zA-Z._+-]*$")
HELP_TIMEOUT_S: int = 10


def load_registry() -> list[dict]:
    try:
        with REGISTRY.open("r", encoding="utf-8") as f:
            return json.load(f)["adapters"]
    except json.JSONDecodeError as e:
        print(f"FATAL: registry.json is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)
    except KeyError:
        print("FATAL: registry.json missing 'adapters' key", file=sys.stderr)
        sys.exit(2)


def check_id_format(aid: str) -> list[str]:
    if not ID_PATTERN.match(aid):
        return [f"[R2] id '{aid}' does not match pattern '<lang>-<lib>@<version>'"]
    return []


def check_command_in_path(cmd: str) -> list[str]:
    if shutil.which(cmd) is None:
        return [f"[C1] command '{cmd}' not found in PATH"]
    return []


def check_command_runs(cmd: str) -> list[str]:
    try:
        r = subprocess.run(
            [cmd, "--help"],
            capture_output=True,
            text=True,
            timeout=HELP_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return [f"[C2] '{cmd} --help' timed out after {HELP_TIMEOUT_S}s"]
    except FileNotFoundError:
        return [f"[C2] command '{cmd}' not found (FileNotFoundError)"]
    except Exception as e:  # pragma: no cover - defensive
        return [f"[C2] '{cmd} --help' raised {type(e).__name__}: {e}"]
    if r.returncode != 0:
        snippet = (r.stderr or r.stdout or "").strip()[:200]
        return [f"[C2] '{cmd} --help' exited {r.returncode}; output={snippet!r}"]
    return []


def check_command_uniqueness(entries: list[dict]) -> list[str]:
    """[G1] no two non-disabled entries may share the same command.

    Rationale: registry id encodes version, but the executable (command) usually
    does not. Two entries that resolve to the same binary would silently call
    the same library version, making version comparison meaningless.
    """
    seen: dict[str, list[str]] = {}
    for e in entries:
        if e.get("disabled"):
            continue
        seen.setdefault(e["command"], []).append(e["id"])
    errs: list[str] = []
    for cmd, ids in seen.items():
        if len(ids) > 1:
            errs.append(
                f"[G1] command '{cmd}' is shared by {len(ids)} non-disabled "
                f"entries: {ids}. Disable old versions or wrap each version "
                f"in its own command (e.g. 'pymupdf-1.23' / 'pymupdf-1.24')."
            )
    return errs


def main() -> int:
    p = argparse.ArgumentParser(description="lint-adapter", add_help=True)
    p.add_argument("adapter_id", nargs="?", help="adapter id; omit for global-only checks")
    p.add_argument(
        "--check-command",
        action="store_true",
        help="also verify <cmd> is in PATH",
    )
    p.add_argument(
        "--check-help",
        action="store_true",
        help="also run <cmd> --help and verify exit 0 (implies --check-command)",
    )
    args = p.parse_args()

    if not REGISTRY.exists():
        print(f"FATAL: registry not found at {REGISTRY}", file=sys.stderr)
        return 2

    entries = load_registry()
    errs: list[str] = []

    errs.extend(check_command_uniqueness(entries))

    if args.adapter_id:
        target = next((e for e in entries if e["id"] == args.adapter_id), None)
        if target is None:
            known = [e["id"] for e in entries]
            print(f"FAIL [R1] id '{args.adapter_id}' not in registry. Known: {known}")
            return 1
        print(
            f"  found: id={target['id']}, "
            f"command={target['command']}, language={target['language']}"
        )
        errs.extend(check_id_format(target["id"]))
        if args.check_command or args.check_help:
            errs.extend(check_command_in_path(target["command"]))
        if args.check_help:
            errs.extend(check_command_runs(target["command"]))
    else:
        if args.check_help:
            print(
                "note: --check-help requires an adapter id; ignored",
                file=sys.stderr,
            )

    if errs:
        for e in errs:
            print(f"FAIL  {e}")
        return 1
    print("OK (all checks passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
