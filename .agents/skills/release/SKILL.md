---
name: release
description: Cuts a nustack release, or a dry run of one that publishes nothing. Use when asked to release nustack or to dry-run a release, such as "release 0.1.0" or "dry-run release 0.1.0".
---

# Release

Each pull request has already added its entry under `CHANGELOG.md`'s `[Unreleased]`, so a release only sets the version and titles that section. A release and a dry run take the same steps up to the last: a dry run stops before anything leaves the machine and shows what would ship.

1. Run `git fetch origin main`, then create a branch from `origin/main`. The step is done when the branch is checked out at `origin/main`'s latest commit with no changes.
2. Run `bun scripts/release.ts bump <version>` with the version the user named. It sets the version in every manifest and titles `[Unreleased]` as `[<version>] - <date>`, with today's date in UTC; it refuses a version not above the current one, or an `[Unreleased]` with no change, and then changes nothing. The step is done when it prints `Set version <version>`, or that the version is already set, and `bun run check` passes.
3. Open the section with a lead: a short paragraph above its first `###` group that tells a reader new to nustack what the release brings. Read the page `bun scripts/release.ts notes` prints as that reader and fix each friction point. The step is done when the lead is there and a cold read of the page finds no friction point.
4. Run `bun scripts/release.ts publish --dry-run`. It prints the tag and the release page the release workflow would publish, or that the version is already released. The step is done when it prints either.
5. For a dry run, show the user `git diff` and the page step 4 printed, then run `git restore .`, switch back to the branch you started on and delete the release branch. The dry run is done when the release branch is gone and `git status` shows no change; nothing was pushed.
6. For a release, commit the changes, push the branch and open a pull request into `main` titled `chore: release <version>`, its description started from `.github/pull_request_template.md`. Once the user merges it, the release workflow publishes the release: it runs `bun scripts/release.ts publish` on `main`, which tags `v<version>` and publishes the page, and does nothing for a version already released. Where the workflow cannot run, run that same command from an up-to-date `main` yourself; it tags the commit that set the version, not `main`'s tip. The step is done when the release page for `v<version>` is published.
