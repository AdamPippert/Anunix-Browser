# Anunix-Browser — developer Makefile.
#
# All targets work from a cold clone. `make deps` creates a venv, installs the
# package, and downloads the Chromium build Playwright needs.

PY ?= python3
VENV ?= .venv
VENV_BIN := $(VENV)/bin
PIP := $(VENV_BIN)/pip
PYTHON := $(VENV_BIN)/python

HOST ?= 127.0.0.1
PORT ?= 9090

.PHONY: help
help:
	@echo "Anunix-Browser make targets:"
	@echo "  make deps     Create venv, install deps, install Playwright Chromium"
	@echo "  make run      Run the anxbrowserd daemon"
	@echo "  make test     Run the unit test suite"
	@echo "  make lint     Run ruff over the source tree"
	@echo "  make clean    Remove build artefacts"
	@echo "  make agent    Run the example agent against a running daemon"
	@echo "  make demo     Spin up daemon + open UI + run example agent"
	@echo "  make desktop-deps   Install Node deps for Tauri desktop app"
	@echo "  make desktop-dev    Hot-reload Tauri desktop window (needs Rust)"
	@echo "  make desktop-build  Release bundle for macOS/Linux"
	@echo "  make desktop-sync   Sync web/static assets → desktop/static"

$(VENV):
	$(PY) -m venv $(VENV)
	$(PIP) install --upgrade pip wheel >/dev/null

.PHONY: deps
deps: $(VENV)
	$(PIP) install -e ".[dev]"
	$(PYTHON) -m playwright install chromium

.PHONY: run
run:
	@if [ ! -d $(VENV) ]; then echo "run 'make deps' first"; exit 1; fi
	ANXB_HOST=$(HOST) ANXB_PORT=$(PORT) $(PYTHON) -m anxbrowser.server

.PHONY: test
test:
	@if [ ! -d $(VENV) ]; then echo "run 'make deps' first"; exit 1; fi
	$(VENV_BIN)/pytest -q

.PHONY: lint
lint:
	@if [ ! -d $(VENV) ]; then echo "run 'make deps' first"; exit 1; fi
	$(VENV_BIN)/ruff check anxbrowser tests examples

.PHONY: agent
agent:
	$(PY) examples/agent_session.py $(URL)

.PHONY: demo
demo:
	./examples/collaborative_demo.sh

.PHONY: clean
clean:
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# ── Desktop app targets ────────────────────────────────────────────────────────
# Sync shared web assets into desktop/static/ before building/running.
.PHONY: desktop-sync
desktop-sync:
	cp web/static/protocol.js desktop/static/protocol.js
	cp web/static/app.js      desktop/static/app.js
	cp web/static/app.css     desktop/static/app.css

# `make desktop-dev` — hot-reload Tauri dev window (requires Rust + Tauri CLI).
.PHONY: desktop-dev
desktop-dev: desktop-sync
	cd desktop && npm run dev

# `make desktop-build` — produce a release bundle under desktop/src-tauri/target/release/.
.PHONY: desktop-build
desktop-build: desktop-sync
	cd desktop && npm run build

# `make desktop-deps` — install Node deps and Tauri CLI for the desktop project.
.PHONY: desktop-deps
desktop-deps:
	cd desktop && npm install
