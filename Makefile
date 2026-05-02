COMMIT  := $(shell git rev-parse --short HEAD 2>/dev/null || echo "none")
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null | sed 's/^v//' || echo "0.2.0-$(COMMIT)")

UV      := uv run
PYTHON  := $(UV) python

.PHONY: install install-tools \
        test test-unit test-cover test-verbose \
        fmt lint type-check \
        ready-tools ready ci \
        pipeline \
        clean \
        check-tools help

.DEFAULT_GOAL := help

# ── Install ──────────────────────────────────────────────────────────────────

install:
	@printf "Installing dependencies...\n"
	@uv sync
	@printf "\033[32mDependencies installed.\033[0m\n"

install-tools:
	@uv sync --extra dev

# ── Test ─────────────────────────────────────────────────────────────────────

test:
	@printf "Running tests...\n"
	@$(UV) pytest tests/ -q
	@printf "\033[32mTests passed.\033[0m\n"

test-unit:
	@$(UV) pytest tests/ -q --no-cov

test-cover:
	@$(UV) pytest tests/ --cov=rate_card --cov-report=term-missing --cov-report=html
	@printf "Coverage report: htmlcov/index.html\n"

test-verbose:
	@$(UV) pytest tests/ -v

# ── Code Quality ─────────────────────────────────────────────────────────────

fmt:
	@printf "Formatting...\n"
	@$(UV) ruff format src/ tests/
	@$(UV) ruff check --select I --fix src/ tests/
	@printf "\033[32mFormatted.\033[0m\n"

lint:
	@printf "Linting...\n"
	@$(UV) ruff check src/ tests/
	@printf "\033[32mLinted.\033[0m\n"

type-check:
	@$(UV) mypy src/rate_card/

# ── Ready (pre-commit quality gate) ──────────────────────────────────────────

ready-tools: fmt lint
	@printf "\033[32mCode quality checks passed.\033[0m\n"

ready: fmt lint type-check test
	@printf "\033[32mReady for commit.\033[0m\n"

# ── CI ────────────────────────────────────────────────────────────────────────

ci: fmt lint type-check test-cover
	@printf "\033[32mCI passed.\033[0m\n"

# ── Pipeline (local smoke test) ───────────────────────────────────────────────

pipeline:
	@printf "Running pipeline against fixture...\n"
	@mkdir -p .cache
	@$(UV) rate-card generate --use-fixture --output .cache/rate-card.json
	@printf "\033[32mPipeline smoke test passed. Output: .cache/rate-card.json\033[0m\n"

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	@rm -rf dist/ .cache/ htmlcov/ .coverage .ruff_cache/ .mypy_cache/ .pytest_cache/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@printf "\033[32mClean.\033[0m\n"

# ── Tools ─────────────────────────────────────────────────────────────────────

check-tools:
	@printf "Checking tools...\n"
	@printf "  python:  %s\n" "$$(python --version 2>&1)"
	@printf "  uv:      %s\n" "$$(uv --version 2>&1)"

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo "llm-rate-card"
	@echo ""
	@echo "Setup:"
	@echo "  make install         Install runtime dependencies"
	@echo "  make install-tools   Install dev dependencies"
	@echo ""
	@echo "Testing and quality:"
	@echo "  make test            Run all tests"
	@echo "  make test-unit       Run tests without coverage"
	@echo "  make test-cover      Tests with coverage report"
	@echo "  make test-verbose    Tests with verbose output"
	@echo "  make fmt             Format code"
	@echo "  make lint            Lint code"
	@echo "  make type-check      Run mypy"
	@echo "  make ready           Pre-commit gate (fmt + lint + type-check + test)"
	@echo "  make ci              Full CI pipeline"
	@echo ""
	@echo "Pipeline:"
	@echo "  make pipeline        Smoke test against fixture, writes .cache/rate-card.json"
	@echo ""
	@echo "Other:"
	@echo "  make clean           Remove artefacts and caches"
	@echo "  make check-tools     Show installed tool versions"
