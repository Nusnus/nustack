/** What both the check and the release hold the plugin to: its version's form and the README steps its release page copies. */

// A plugin version, <major>.<minor>.<patch>, as Semantic Versioning writes one with no pre-release or build part.
export const VERSION = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/

// README's steps a reader needs to try the release; the third, which turns nus-mode on for a project, stays in README.
export const PAGE_STEPS = Object.freeze(["### 1️⃣ Install", "### 2️⃣ Use"])
