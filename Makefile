.PHONY: help bun uv zip bun-lock install check mutate bundle smoke clean
export UV_LOCKED := 1

help: ## List the targets to run
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

bun:
	@command -v bun >/dev/null || { echo 'Bun is missing; install it from https://bun.sh/docs/installation, then rerun the command that stopped' >&2; exit 1; }

uv:
	@command -v uv >/dev/null || { echo 'uv is missing; install it from https://docs.astral.sh/uv/getting-started/installation/, then rerun the command that stopped' >&2; exit 1; }

zip:
	@command -v zip >/dev/null && command -v unzip >/dev/null || { echo 'zip or unzip is missing; install both with your system package manager, such as apt-get install zip unzip, then rerun the command that stopped' >&2; exit 1; }

# $(call bun-install,<folder>/) installs from the bun.lock in that folder, or
# the repository's when the folder is empty. bun install --frozen-lockfile
# passes where no lock exists, writing none and resolving every package afresh,
# so the missing lock is caught first (https://bun.com/docs/pm/cli/install).
define bun-install
@test -f $(1)bun.lock || { echo '$(1)bun.lock is missing; restore it with git restore $(1)bun.lock, or after git rm with git restore --staged --worktree $(1)bun.lock, or run bun install$(if $(1), --cwd $(1)) and git add $(1)bun.lock, then rerun the command that stopped' >&2; exit 1; }
bun install$(if $(1), --cwd $(1)) --frozen-lockfile
endef

bun-lock: bun
	$(call bun-install,)

install: uv bun-lock ## Install the harness, its tools and the commit hooks
	uv sync
	uv run pre-commit install

# CI passes PRE_COMMIT_FLAGS to pre-commit (.github/workflows/ci.yml); locally
# it is empty.
check: bun uv zip ## Run every pre-commit-stage hook over every file, fixing what the tools can fix
	uv run pre-commit run --all-files $(PRE_COMMIT_FLAGS)

mutate: uv ## Run mutmut over the harness, failing on each mutant the tests let live
	uv run mutmut run
	@! uv run mutmut results | grep -v ': timeout$$' || { echo 'mutmut left the mutants above alive; give each a test that kills it, then rerun make mutate' >&2; exit 1; }

bundle: uv ## Build dist/nustack-<version>.zip for upload
	uv run nustack bundle

# The hosts are large downloads, so only make smoke installs them, from their
# own lock.
smoke: bun zip bundle ## Run the release zip in Claude Code and OpenCode against a fake model
	$(call bun-install,tests/fixtures/smoke/)
	bun --config=tests/fixtures/smoke/bunfig.toml test

clean: ## Remove build and cache output
	rm -rf dist mutants .import_linter_cache .pytest_cache .ruff_cache .coverage
	find src tests -name __pycache__ -prune -exec rm -rf {} +
