#!/usr/bin/env bash
# 检查所有被测语言运行时是否齐备
# 仅给出提示，不强制；orchestrator 自身只用 Python。

set +e
echo "== Language runtime check =="

check() {
  local name=$1; shift
  local cmd=$1; shift
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "  [OK]   %-10s -> %s\n" "$name" "$(command -v "$cmd")"
  else
    printf "  [MISS] %-10s (looking for: %s)\n" "$name" "$cmd"
  fi
}

check Python    python3
check Python    python
check Node      node
check Java      java
check Go        go
check Rust      cargo
check .NET      dotnet
check C++       cmake
check C++       g++
check Ruby      ruby
check Kotlin    kotlin

echo
echo "Tip: missing runtimes won't fail this check, but their adapters will be skipped at run time."
