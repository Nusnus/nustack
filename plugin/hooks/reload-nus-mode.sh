#!/bin/sh
# Puts nus-mode's text back in context after a summarization, in a session that loaded it before. On input or an
# installed SKILL.md it cannot use, it exits 1 with the fix on stderr.
# Claude Code passes the hook's input as a JSON object on stdin:
# https://code.claude.com/docs/en/hooks#common-input-fields
# POSIX sh has no JSON parser, so the script reads the two string fields it needs, and fails on an escape it cannot
# undo.
# It reads its input, the transcript and SKILL.md in milliseconds, so the timeout in hooks.json stops it far sooner
# than Claude Code's default: https://code.claude.com/docs/en/hooks#common-fields
set -eu

broken_install() {
  fail "$1, or reinstall the nustack plugin"
}

fail() {
  printf 'nustack reload-nus-mode: %s\n' "$1" >&2
  exit 1
}

field() {
  printf '%s\n' "$input" | sed -n -E 's/.*"'"$1"'":"(([^"\\]|\\.)*)".*/\1/p' | head -n 1
}

input=$(cat)
# Only the SessionStart input after a summarization has the source compact, so any other input, or one without a
# source, has nothing to reload: https://code.claude.com/docs/en/hooks#sessionstart-input
[ "$(field source)" = compact ] || exit 0
escaped_transcript_path=$(field transcript_path)
[ -n "$escaped_transcript_path" ] || fail "the hook input has no transcript_path; run the hook from Claude Code, which passes one"
case $(printf '%s' "$escaped_transcript_path" | sed -E 's/\\["\\/]//g') in
  *\\*) fail "transcript_path $escaped_transcript_path holds a JSON escape other than \\\", \\\\ or \\/; move the session to a path without one" ;;
esac
transcript=$(printf '%s' "$escaped_transcript_path" | sed -E 's/\\(["\\/])/\1/g')
[ -f "$transcript" ] || fail "transcript_path $transcript is no file; check that the file exists"
[ -r "$transcript" ] || fail "transcript_path $transcript cannot be read; make it readable"
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || fail "CLAUDE_PLUGIN_ROOT is unset; run the hook from Claude Code, which sets it"
folder="$CLAUDE_PLUGIN_ROOT/skills/nus-mode"
skill="$folder/SKILL.md"
[ -e "$skill" ] || broken_install "$skill does not exist; restore it"
[ -f "$skill" ] || broken_install "$skill is no file; restore it as a file"
[ -r "$skill" ] || broken_install "$skill cannot be read; make it readable"
# scripts/check.ts accepts CRLF lines, so the hook reads them as LF. It also holds SKILL.md to a frontmatter
# block that opens on its first line and closes, then a body that opens with the mode's title.
text=$(tr -d '\r' <"$skill")
[ "$(printf '%s\n' "$text" | head -n 1)" = --- ] || broken_install "$skill has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings"
[ "$(printf '%s\n' "$text" | grep -c '^---$')" -ge 2 ] || broken_install "$skill opens with --- and never closes; end it with a --- line"
# The body drops its leading blank lines, as Claude Code's own skill load prints it in
# tests/fixtures/claude-code/transcripts/invoked.jsonl.
body=$(printf '%s\n' "$text" | awk 'fences >= 2 { print; next } /^---$/ { fences++ }' | sed '/./,$!d')
[ -n "$body" ] || broken_install "$skill has a blank body; give it nus-mode's text, which opens with the line # nus-mode"
title=$(printf '%s\n' "$body" | head -n 1)
[ "$title" = "# nus-mode" ] || broken_install "$skill has a body that does not open with nus-mode's title; open it with # nus-mode"
# A skill load leaves a meta record whose text gives the skill's folder, then its body, title first; a prompt, a tool
# result, another skill's body that quotes the mode, or another plugin's skill of the same name leaves no meta record
# that names this plugin's folder, as tests/fixtures/claude-code/transcripts records. JSON escapes a folder's \ and ",
# and writes each line break as \n; a CRLF SKILL.md's body keeps its \r\n after the \n\n that ends the folder line.
escaped_folder=$(printf '%s' "$folder" | sed 's/\\/\\\\/g; s/"/\\"/g')
lf="\"text\":\"Base directory for this skill: $escaped_folder\\n\\n$title\\n"
crlf="\"text\":\"Base directory for this skill: $escaped_folder\\n\\n$title\\r\\n"
if grep -F -e "$lf" -e "$crlf" -- "$transcript" | grep -qF '"isMeta":true'; then
  # The mode's links are relative to its folder, so the folder leads its body, as Claude Code's own skill load gives it
  # in tests/fixtures/claude-code/transcripts/invoked.jsonl.
  printf 'This session worked in nus-mode before its context was summarized. nus-mode follows; keep working in it.\n\nBase directory for this skill: %s\n\n%s\n' "$folder" "$body"
fi
