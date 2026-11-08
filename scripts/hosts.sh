#!/usr/bin/env bash
# Installs this checkout's plugin in the latest Claude Code, as its users do, and in the latest OpenCode through a
# config file pointed at it, and checks each offers every folder under plugin/skills, with OpenCode hiding the
# principle and language skills from the model.
set -euo pipefail
if (( $# > 0 )); then
  echo "scripts/hosts.sh: takes no arguments; got $*" >&2
  exit 2
fi
root=$(pwd)
work=$(mktemp -d)
server=
trap '[[ -n $server ]] && kill "$server"; rm -rf "$work"' EXIT
export HOME=$work/home XDG_CONFIG_HOME=$work/config XDG_DATA_HOME=$work/data XDG_STATE_HOME=$work/state
mkdir -p "$HOME"
# A password set outside would hold the server to it, not to the one this script reads from its log.
unset OPENCODE_PASSWORD
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
# OpenCode lists the plugin's skills only once it has loaded the plugin, seconds after its server starts.
for _ in $(seq 60); do
  skills=$("$bin/opencode" api --server "$url" GET /api/skill \
    | jq --arg plugin "$root/plugin/" '.data |= map(select(.path | startswith($plugin)))')
  [[ $(jq '.data | length' <<< "$skills") -gt 0 ]] && break
  sleep 1
done
compare OpenCode "$(jq -r '.data[].id' <<< "$skills" | sort)"
hidden=$(jq -r '.data[] | select(.autoinvoke == false) | .id' <<< "$skills" | sort)
if [[ $hidden != "$(grep -E '^(principle|language)-' <<< "$expected")" ]]; then
  echo "OpenCode hides these skills from the model, where it should hide exactly the principle and language skills:" >&2
  echo "${hidden:-none}" >&2
  status=1
fi
exit $status
