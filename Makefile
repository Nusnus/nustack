.DEFAULT_GOAL := help
.PHONY: help bun install check bundle clean
export UV_LOCKED := 1

help: ## List every target
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

bun:
	@command -v bun >/dev/null || { echo 'Bun is missing; install it from https://bun.sh/docs/installation, then rerun make' >&2; exit 1; }

install: bun ## Install the harness, its tools and the commit hooks
	uv sync
	bun install --frozen-lockfile
	uv run pre-commit install

check: bun ## Run every pre-commit hook over every file, fixing what the tools can fix
	bun install --frozen-lockfile
	uv run pre-commit run --all-files --show-diff-on-failure

bundle: ## Build dist/nustack-<version>.zip for upload
	uv run nustack bundle

clean: ## Remove build and cache output
	rm -rf dist .pytest_cache .ruff_cache .coverage
	find src tests -name __pycache__ -prune -exec rm -rf {} +
