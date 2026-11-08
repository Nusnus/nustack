.PHONY: help bun uv zip unzip bun-lock smoke-lock install check bundle smoke clean
export UV_LOCKED := 1

help: ## List the targets to run
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-15s %s\n", $$1, $$2}'

bun:
	@command -v bun >/dev/null || { echo 'Bun is missing; install it from https://bun.sh/docs/installation, then rerun the command that stopped' >&2; exit 1; }

uv:
	@command -v uv >/dev/null || { echo 'uv is missing; install it from https://docs.astral.sh/uv/getting-started/installation/, then rerun the command that stopped' >&2; exit 1; }

# make check's tests zip a fixture (tests/integration/fixtures/bundle.test.ts).
zip:
	@command -v zip >/dev/null || { echo 'zip is missing; install it with your system package manager, such as apt-get install zip, then rerun the command that stopped' >&2; exit 1; }

# make check's tests list the release zip's entries
# (tests/integration/scripts/release.test.ts) and unpack a fixture's zip, and
# make smoke unpacks the release zip (tests/fixtures/bundle.ts).
unzip:
	@command -v unzip >/dev/null || { echo 'unzip is missing; install it with your system package manager, such as apt-get install unzip, then rerun the command that stopped' >&2; exit 1; }

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

# The hosts are large downloads, so only make smoke installs them, from their own
# lock.
smoke-lock: bun
	$(call bun-install,tests/fixtures/smoke/)

install: uv bun-lock ## Install the tools and the commit hooks
	uv sync
	uv run pre-commit install

# CI passes PRE_COMMIT_FLAGS to pre-commit (.github/workflows/ci.yml); locally
# it is empty.
check: bun uv zip unzip ## Run every pre-commit-stage hook over every file, fixing what the tools can fix
	uv run pre-commit run --all-files $(PRE_COMMIT_FLAGS)

# scripts/release.ts bundle says how it builds the zip. It imports the Markdown parser, so it installs bun.lock first.
bundle: bun-lock ## Build dist/nustack-<version>.zip from the committed plugin/
	bun scripts/release.ts bundle

# Claude Code's own validator (https://code.claude.com/docs/en/plugins/cli-reference)
# first checks the release zip, unpacked, since the zip is what installs. It runs
# here, not as a commit hook: it comes with Claude Code, which only make smoke
# installs, and a commit builds no zip. A host's cold start and its turns take
# seconds, so a stalled host stops its test after two minutes.
smoke: unzip smoke-lock bundle ## Validate the release zip's plugin, then run the zip in Claude Code and OpenCode against a fake model
	unpacked=$$(mktemp -d) && trap 'rm -rf "$$unpacked"' EXIT && unzip -q dist/nustack-*.zip -d "$$unpacked" && tests/fixtures/smoke/node_modules/.bin/claude plugin validate "$$unpacked" --strict
	bun --config=tests/fixtures/smoke/bunfig.toml test --timeout=120000

clean: ## Remove build output
	rm -rf dist
