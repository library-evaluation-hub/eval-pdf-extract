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
    NULLDEV := NUL
else
    DETECTED_OS := Unix
    NULLDEV := /dev/null
endif

# ---- Tools -----------------------------------------------------------
UV ?= uv

# ---- Phony -----------------------------------------------------------
.PHONY: help info install check-env lint test integration-test run run-adapter webui \
        webui-dev webui-build webui-install validate-corpus add-fixture update-fixture lint-adapter clean

# ---- Help ------------------------------------------------------------
help:                       ## Show this help
	@echo "Available targets:"
	@echo "  install                 Install orchestrator + webui + dev deps via uv"
	@echo "  check-env               Verify all language runtimes are available"
	@echo "  lint                    Run ruff + mypy on src/"
	@echo "  test                    Run Python unit tests"
	@echo "  integration-test        Run real adapter x fixture (slow)"
	@echo "  run                     Run benchmark with all adapters on all fixtures"
	@echo "  run-adapter ADAPTER=.. Run benchmark for a single adapter on 01_* fixtures"
	@echo "  webui                   Start webui server (default port 8765)"
	@echo "  webui-install           Install frontend npm dependencies"
	@echo "  webui-build             Build frontend (npm run build)"
	@echo "  webui-dev               Start both backend + Vite dev server (use two terminals)"
	@echo "  validate-corpus         Validate corpus/manifest.json vs fixtures on disk"
	@echo "  add-fixture             Create a fixture from a PDF (use: make add-fixture INPUT=.. CATEGORY=.. SLUG=..)"
	@echo "  update-fixture          Regenerate expected.json for a fixture (use: make update-fixture FIXTURE=.. ADAPTER=..)"
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

run-adapter:                ## Run benchmark for ADAPTER=<id> on 01_* fixtures (version optional)
ifndef ADAPTER
	$(error Usage: make run-adapter ADAPTER=<adapter-id>  e.g. make run-adapter ADAPTER=python-pymupdf)
endif
	$(UV) run python -m orchestrator run --corpus corpus/ --adapters $(ADAPTER) --fixture-glob "01_*" --workers 1

webui:                      ## Start webui server (serves built frontend from dist/)
	$(UV) run python -m webui.backend.main --host 127.0.0.1 --port 8765

webui-install:              ## Install frontend npm dependencies
	cd webui/frontend && npm install

webui-build:                ## Build frontend (npm run build)
	cd webui/frontend && npm run build

webui-dev:                  ## Start backend only (run 'npm run dev' in webui/frontend/ separately)
	@echo "Starting backend on http://127.0.0.1:8765"
	@echo "In another terminal: cd webui/frontend && npm run dev"
	$(UV) run python -m webui.backend.main --host 127.0.0.1 --port 8765

# ---- Validation ------------------------------------------------------
validate-corpus:            ## Validate corpus/manifest.json vs fixtures on disk
	$(UV) run python -m orchestrator validate-corpus

add-fixture:                ## Create a fixture from a PDF (CONFIG=yaml + optional overrides, or INPUT=.. CATEGORY=.. SLUG=..)
ifdef CONFIG
	$(UV) run python -m orchestrator add-fixture --config $(CONFIG) \
		$(if $(INPUT),--input $(INPUT)) $(if $(CATEGORY),--category $(CATEGORY)) \
		$(if $(SLUG),--slug $(SLUG)) $(if $(TITLE),--title "$(TITLE)") \
		$(if $(LICENSE),--license $(LICENSE)) $(if $(AUTHOR),--author $(AUTHOR)) \
		$(if $(TAGS),--tags "$(TAGS)") $(if $(ADAPTER),--adapter $(ADAPTER))
else
ifndef INPUT
	$(error Usage: make add-fixture CONFIG=<yaml> [INPUT=<pdf> ...] OR make add-fixture INPUT=<pdf> CATEGORY=<category> SLUG=<slug>)
endif
ifndef CATEGORY
	$(error Usage: make add-fixture CONFIG=<yaml> [INPUT=<pdf> ...] OR make add-fixture INPUT=<pdf> CATEGORY=<category> SLUG=<slug>)
endif
ifndef SLUG
	$(error Usage: make add-fixture CONFIG=<yaml> [INPUT=<pdf> ...] OR make add-fixture INPUT=<pdf> CATEGORY=<category> SLUG=<slug>)
endif
	$(UV) run python -m orchestrator add-fixture --input $(INPUT) --category $(CATEGORY) --slug $(SLUG) \
		$(if $(TITLE),--title "$(TITLE)") $(if $(LICENSE),--license $(LICENSE)) \
		$(if $(AUTHOR),--author $(AUTHOR)) $(if $(TAGS),--tags "$(TAGS)") \
		$(if $(ADAPTER),--adapter $(ADAPTER))
endif

update-fixture:              ## Regenerate expected.json for a fixture (FIXTURE=.. [ADAPTER=..] [NOTE=..])
ifndef FIXTURE
	$(error Usage: make update-fixture FIXTURE=<fixture-id> [ADAPTER=<adapter-id>] [NOTE=..])
endif
	$(UV) run python -m orchestrator update-fixture --fixture $(FIXTURE) \
		$(if $(ADAPTER),--adapter $(ADAPTER)) $(if $(NOTE),--note "$(NOTE)")

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
