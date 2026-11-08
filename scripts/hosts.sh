#!/usr/bin/env bash
# Installs the plugin in the latest Claude Code and OpenCode, as their users do, and checks each offers every
# folder under plugin/skills, with OpenCode hiding the principle and language skills from the model.
set -euo pipefail
root=$(pwd)
work=$(mktemp -d)
server=
trap '[[ -n $server ]] && kill "$server"; rm -rf "$work"' EXIT
export HOME=$work/home XDG_CONFIG_HOME=$work/config XDG_DATA_HOME=$work/data XDG_STATE_HOME=$work/state
mkdir -p "$HOME"
expected=$(ls plugin/skills | sort)
status=0
compare() {
  if [[ $2 != "$expected" ]]; then
    echo "$1 offers a different set of skills than plugin/skills holds:" >&2
    diff <(echo "$expected") <(echo "$2") >&2 || true
    status=1
  fi
}
(cd "$work" && bun add --silent @anthropic-ai/claude-code@latest @opencode/cli@latest --trust)
bin=$work/node_modules/.bin

"$bin/claude" plugin validate "$root" --strict
"$bin/claude" plugin validate "$root/plugin" --strict
"$bin/claude" plugin marketplace add "$root" > /dev/null
"$bin/claude" plugin install nustack@nustack > /dev/null
# `plugin details` has no JSON output; its "Skills (<n>)" line lists the names, comma-separated.
offered=$("$bin/claude" plugin details nustack@nustack | sed -nE 's/^ *Skills \([0-9]+\) +//p' | tr -d ' ' | tr ',' '\n' | sort)
compare "Claude Code" "$offered"

project=$work/project
mkdir -p "$project"
printf '{"plugins": ["%s"]}\n' "$root/plugin" > "$project/opencode.json"
(cd "$project" && exec "$bin/opencode" serve --port 0 > "$work/serve.log" 2>&1) &
server=$!
for _ in $(seq 60); do grep -q "server password" "$work/serve.log" && break; sleep 1; done
if ! grep -q "server password" "$work/serve.log"; then
  echo "OpenCode did not start its server within 60 seconds; its log follows:" >&2
  cat "$work/serve.log" >&2
  exit 1
fi
url=$(grep -oE 'listening on \S+' "$work/serve.log" | cut -d' ' -f3)
OPENCODE_PASSWORD=$(grep -oE 'server password \S+' "$work/serve.log" | cut -d' ' -f3)
export OPENCODE_PASSWORD
# OpenCode lists its own skills at once and the plugin's only once it has loaded the plugin, seconds later.
for _ in $(seq 60); do
  skills=$("$bin/opencode" api --server "$url" GET /api/skill --param "directory=$project" \
    | jq --arg plugin "$root/plugin/" '.data |= map(select(.path | startswith($plugin)))')
  [[ $(jq '.data | length' <<< "$skills") -gt 0 ]] && break
  sleep 1
done
compare OpenCode "$(jq -r '.data[].id' <<< "$skills" | sort)"
visible=$(jq -r '.data[] | select(.autoinvoke == true) | .id | select(test("^(principle|language)-"))' <<< "$skills")
if [[ -n $visible ]]; then
  echo "OpenCode offers these principle or language skills to the model: $visible" >&2
  status=1
fi
exit $status
