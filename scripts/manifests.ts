/**
 * The plugin manifests of Claude Code, Cursor and Devin, which hold the same fields, and the one whose version a release
 * publishes; OpenCode reads plugin/package.json.
 */
export const MANIFESTS = [
  "plugin/.claude-plugin/plugin.json",
  "plugin/.cursor-plugin/plugin.json",
  "plugin/.devin-plugin/plugin.json",
] as const
// The release workflow runs on a change to this manifest, so its version is the one a release publishes.
export const VERSION_SOURCE = MANIFESTS[0]
