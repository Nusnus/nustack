/**
 * The skills the records in vendored/ copy into the plugin, which every host lists beside nustack's own. Written out
 * apart from the records, so a test that expects them fails when a record drops one.
 */
export const VENDORED_SKILLS = [
  "defuddle",
  "json-canvas",
  "knap",
  "obsidian-bases",
  "obsidian-cli",
  "obsidian-markdown",
] as const
