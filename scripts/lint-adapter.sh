#!/usr/bin/env bash
# 静态校验某个 adapter 是否符合 contract/adapter-protocol.md
# 把参数透传给 scripts/lint_adapter.py —— 真正的契约校验在 Python 里。
# 默认启用 --check-command --check-help 以覆盖全部检查 (G1/R2/C1/C2)。
# 当 orchestrator 落地后，本文件将成为 Makefile → `python -m orchestrator
# lint-adapter` 的薄壳；本脚本是 v1 中间态。

set -e
ADAPTER_ID="${1:-}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== lint-adapter (sh) =="

if [ -n "$ADAPTER_ID" ]; then
  exec uv run --directory "$REPO_ROOT" python "$REPO_ROOT/scripts/lint_adapter.py" \
    "$ADAPTER_ID" --check-command --check-help
fi

exec uv run --directory "$REPO_ROOT" python "$REPO_ROOT/scripts/lint_adapter.py" \
  --check-command --check-help
