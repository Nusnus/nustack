#!/bin/sh
# Puts nus-mode's text back in context after a summarization, in a session that loaded it before. On input or an
# installed SKILL.md it cannot use, it exits 1 with the fix on stderr.
# Claude Code passes the hook's input as a JSON object on stdin:
# https://code.claude.com/docs/en/hooks#common-input-fields
# POSIX sh has no JSON parser, so the script reads the two string fields it needs, and fails on an escape it cannot
# undo.
set -eu

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
raw=$(field transcript_path)
[ -n "$raw" ] || fail "the hook input has no transcript_path; run the hook from Claude Code, which passes one"
case $(printf '%s' "$raw" | sed -E 's/\\["\\/]//g') in
  *\\*) fail "transcript_path holds a JSON escape other than \\\", \\\\ or \\/; move the session to a path without one" ;;
esac
transcript=$(printf '%s' "$raw" | sed -E 's/\\(["\\/])/\1/g')
[ -f "$transcript" ] && [ -r "$transcript" ] || fail "the transcript that transcript_path names is no readable file; check that the file exists"
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || fail "CLAUDE_PLUGIN_ROOT is unset; run the hook from Claude Code, which sets it"
folder="$CLAUDE_PLUGIN_ROOT/skills/nus-mode"
skill="$folder/SKILL.md"
[ -r "$skill" ] || fail "nus-mode's SKILL.md cannot be read; reinstall the nustack plugin"
# nustack check accepts CRLF lines, so the body reads them as LF, and drops its leading blank lines, as Claude Code's
# own skill load prints it in tests/fixtures/claude-code/transcripts/invoked.jsonl.
body=$(tr -d '\r' <"$skill" | awk 'fences >= 2 { print; next } /^---$/ { fences++ }' | sed '/./,$!d')
# nustack check holds the body's opening line to the mode's title.
title=$(printf '%s\n' "$body" | head -n 1)
[ "$title" = "# nus-mode" ] || fail "nus-mode's SKILL.md does not open with its title; reinstall the nustack plugin"
# A skill load leaves a meta record whose text gives the skill's folder, then its body, title first; a prompt, a tool
# result, another skill's body that quotes the mode, or another plugin's skill of the same name leaves no record that
# names this plugin's folder, as tests/fixtures/claude-code/transcripts records. JSON escapes a folder's \ and ", and
# writes each line break as \n, or \r\n from a CRLF file.
named=$(printf '%s' "$folder" | sed 's/\\/\\\\/g; s/"/\\"/g')
lf="\"text\":\"Base directory for this skill: $named\\n\\n$title\\n"
crlf="\"text\":\"Base directory for this skill: $named\\r\\n\\r\\n$title\\r\\n"
if grep -F -e "$lf" -e "$crlf" -- "$transcript" | grep -qF '"isMeta":true'; then
  # The mode's links are relative to its folder, so the folder leads its body, as Claude Code's own skill load gives it
  # in tests/fixtures/claude-code/transcripts/invoked.jsonl.
  printf 'This session worked in nus-mode before its context was summarized. nus-mode follows; keep working in it.\n\nBase directory for this skill: %s\n\n%s\n' "$folder" "$body"
fi
