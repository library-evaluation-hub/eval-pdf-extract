# eval-pdf-extract — Makefile
#
# 跨平台：
#   - Linux / macOS : 调用 .sh 脚本
#   - Windows       : 调用 .ps1 脚本（pwsh 7+ 优先；找不到则回退 Windows PowerShell 5.1）
# Python 工具链全部走 uv（用户已用 uv 初始化 3.12 环境）。
#
# 用法：
#   make help              查看所有 target
#   make install           uv sync --extra dev --extra webui
#   make check-env         检查各语言运行时
#   make run               跑全量 benchmark
#   make webui             起 webui 服务
#   make lint              ruff + mypy
#   make test              pytest
#   make integration-test  跑真实 adapter × fixture（耗时）
#   make lint-adapter ADAPTER=python-pymupdf@1.24.0
#   make clean             清构建产物 + results/*

# ---- OS detection ----------------------------------------------------
ifeq ($(OS),Windows_NT)
    DETECTED_OS := Windows
    POWERSHELL := pwsh
    PS_RUN := $(POWERSHELL) -NoProfile -ExecutionPolicy Bypass
    NULLDEV := nul
else
    DETECTED_OS := Unix
    NULLDEV := /dev/null
endif

# ---- Tools -----------------------------------------------------------
UV ?= uv

# ---- Phony -----------------------------------------------------------
.PHONY: help info install check-env lint test integration-test run webui \
        validate-corpus lint-adapter clean

# ---- Help ------------------------------------------------------------
help:                       ## Show this help
	@echo "Available targets:"
	@echo "  install                 Install orchestrator + webui + dev deps via uv"
	@echo "  check-env               Verify all language runtimes are available"
	@echo "  lint                    Run ruff + mypy on src/"
	@echo "  test                    Run Python unit tests"
	@echo "  integration-test        Run real adapter x fixture (slow)"
	@echo "  run                     Run benchmark with all adapters on all fixtures"
	@echo "  webui                   Start webui server (default port 8765)"
	@echo "  validate-corpus         Validate corpus/manifest.json vs fixtures on disk"
	@echo "  lint-adapter ADAPTER=.. Static check that an adapter conforms to the contract"
	@echo "  clean                   Remove build artifacts and results/ contents"
	@echo "  info                    Show detected environment"

# ---- Info ------------------------------------------------------------
info:                       ## Show detected environment
	@echo "DETECTED_OS:   $(DETECTED_OS)"
	@echo "UV:            $(UV) ($(shell $(UV) --version 2>$(NULLDEV) || echo 'not found'))"
	@echo "Python (uv):   $(shell $(UV) run python -V 2>$(NULLDEV) || echo 'not synced')"
	@echo "POWERSHELL:    $(POWERSHELL)"

# ---- Install ---------------------------------------------------------
install:                    ## Install orchestrator + webui + dev deps via uv
	$(UV) sync --extra dev --extra webui

# ---- Env check -------------------------------------------------------
check-env:                  ## Verify all language runtimes are available
ifeq ($(OS),Windows_NT)
	@$(PS_RUN) -File scripts/check-env.ps1
else
	@bash scripts/check-env.sh
endif

# ---- Lint / test -----------------------------------------------------
lint:                       ## Run ruff + mypy on src/
	$(UV) run ruff check src
	$(UV) run mypy src

test:                       ## Run Python unit tests
	$(UV) run pytest -q

integration-test:            ## Run real adapter x fixture smoke test (slow)
	$(UV) run python -m orchestrator run --corpus corpus/ --adapters all --fixture-glob "01_*" --workers 1

# ---- Run / UI --------------------------------------------------------
run:                        ## Run benchmark with all adapters on all fixtures
	$(UV) run python -m orchestrator run --corpus corpus/ --adapters all

webui:                      ## Start webui server
	$(UV) run python -m webui.backend.main --host 127.0.0.1 --port 8765

# ---- Validation ------------------------------------------------------
validate-corpus:            ## Validate corpus/manifest.json vs fixtures on disk
	$(UV) run python -m orchestrator validate-corpus

lint-adapter:               ## Static check that an adapter conforms to the contract
ifndef ADAPTER
	$(error Usage: make lint-adapter ADAPTER=<adapter-id>)
endif
ifeq ($(OS),Windows_NT)
	@$(PS_RUN) -File scripts/lint-adapter.ps1 $(ADAPTER)
else
	@bash scripts/lint-adapter.sh $(ADAPTER)
endif

# ---- Clean -----------------------------------------------------------
clean:                      ## Remove build artifacts and results/ contents
	$(UV) run python scripts/clean.py
