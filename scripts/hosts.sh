#!/usr/bin/env bash
# Installs this checkout's plugin in the latest Claude Code, as its users do, and in the latest OpenCode through a
# config file pointed at it, and checks each offers every folder under plugin/skills/, with OpenCode hiding the
# principle and language skills from the model.
set -euo pipefail
# The shell gives a status over 128 to a tool a signal kills, which a command substitution can leave with no message,
# so this says that one failed:
# https://www.gnu.org/software/bash/manual/html_node/Exit-Status.html
trap 'failure=$?; (( failure <= 128 )) || echo "scripts/hosts.sh: a tool it called failed with status $failure" >&2' ERR
if (( $# > 0 )); then
  echo "scripts/hosts.sh: takes no arguments; got $*" >&2
  exit 2
fi
# The physical path, as OpenCode gives each skill's, so a checkout reached through a symlink compares equal.
root=$(pwd -P)
work=$(mktemp -d)
# mktemp follows a relative TMPDIR, and Bun and OpenCode's server run in other folders:
# https://www.gnu.org/software/coreutils/manual/html_node/mktemp-invocation.html
[[ $work == /* ]] || work=$root/$work
server=
# A server that has already exited fails kill, where set -e would end the trap before it removes the folder, and one
# that is still stopping can write into the folder while rm removes it, so the trap waits for it first:
# https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html
trap '[[ -z $server ]] || { kill "$server" 2> /dev/null; wait "$server"; } || true; rm -rf "$work"' EXIT
# Starts Bun and each host with PATH alone of the variables set outside, and with a home and a temporary folder inside
# this script's own. Any other variable set outside could move a file of theirs out of that folder or change what a
# host offers there, as CLAUDE_CONFIG_DIR moves Claude Code's install, NODE_COMPILE_CACHE the cache of the Node that
# runs the hosts' install scripts, and OPENCODE_PASSWORD holds OpenCode's server to a password this script does not
# read from its log. sh starts each command, since env takes a word that holds = for a variable, as a host's path can;
# it adds its own PWD, and SHLVL where it is Bash:
# https://code.claude.com/docs/en/env-vars
# https://nodejs.org/api/cli.html#node_compile_cachedir
# https://opencode.ai/docs/migrate-v1/#server-authentication
# https://pubs.opengroup.org/onlinepubs/9699919799/utilities/env.html
isolated=(env -i PATH="$PATH" HOME="$work/home" TMPDIR="$work/tmp" sh -c 'exec "$@"' sh)
mkdir -p "$work/home" "$work/tmp"
expected=$(ls plugin/skills | sort)
status=0
compare() {
  if [[ $2 != "$expected" ]]; then
    echo "$1 offers a different set of skills than plugin/skills/ holds:" >&2
    diff <(echo "$expected") <(echo "$2") >&2 || true
    status=1
  fi
}
# Bun adds a package to the nearest package.json above a folder that holds none.
echo '{}' > "$work/package.json"
"${isolated[@]}" bun add --cwd "$work" --silent @anthropic-ai/claude-code@latest @opencode/cli@latest --trust
bin=$work/node_modules/.bin

"${isolated[@]}" "$bin/claude" plugin validate "$root" --strict
"${isolated[@]}" "$bin/claude" plugin validate "$root/plugin" --strict
"${isolated[@]}" "$bin/claude" plugin marketplace add "$root" > /dev/null
"${isolated[@]}" "$bin/claude" plugin install nustack@nustack > /dev/null
# `plugin details` has no JSON output; its "Skills (<n>)" line lists the names, comma-separated:
# https://code.claude.com/docs/en/plugins/measure#measure-what-a-plugin-costs
offered=$("${isolated[@]}" "$bin/claude" plugin details nustack@nustack | sed -nE 's/^ *Skills \([0-9]+\) +//p' | tr -d ' ' | tr ',' '\n' | sort)
compare "Claude Code" "$offered"

project=$work/project
mkdir -p "$project"
jq -n --arg plugin "$root/plugin" '{plugins: [$plugin]}' > "$project/opencode.json"
# The server's shell creates the log only once it runs, and the first read below may come sooner.
touch "$work/serve.log"
(cd "$project" && exec "${isolated[@]}" "$bin/opencode" serve --port 0 > "$work/serve.log" 2>&1) &
server=$!
limit=60
# Prints the word that follows a phrase in the server's log, or nothing while the log holds no such phrase.
logged() { sed -nE "s/.*$1 ([^[:space:]]+).*/\1/p" "$work/serve.log"; }
for (( turn = 0; turn < limit; turn++ )); do
  url=$(logged "listening on")
  password=$(logged "server password")
  [[ -n $url && -n $password ]] && break
  sleep 1
done
if [[ -z $url || -z $password ]]; then
  echo "OpenCode's server logged no address or no password within $limit seconds; its log follows:" >&2
  cat "$work/serve.log" >&2
  exit 1
fi
# Runs a command with the hosts' variables and the server's password. The password goes in through standard input,
# since any user of the machine can read the arguments a command starts with:
# https://pubs.opengroup.org/onlinepubs/9699919799/utilities/ps.html
with_password() {
  "${isolated[@]}" sh -c 'read -r OPENCODE_PASSWORD && export OPENCODE_PASSWORD && exec "$@"' sh "$@" <<< "$password"
}
# OpenCode lists the plugin's skills only once it has loaded the plugin, seconds after its server starts.
for (( turn = 0; turn < limit; turn++ )); do
  skills=$(with_password "$bin/opencode" api --server "$url" GET /api/skill \
    | jq --arg plugin "$root/plugin/" '.data |= map(select(.path | startswith($plugin)))')
  count=$(jq '.data | length' <<< "$skills")
  (( count > 0 )) && break
  sleep 1
done
if (( count == 0 )); then
  echo "OpenCode's server listed no skill of the plugin within $limit seconds; its log follows:" >&2
  cat "$work/serve.log" >&2
  exit 1
fi
offered=$(jq -r '.data[].id' <<< "$skills" | sort)
compare OpenCode "$offered"
hidden=$(jq -r '.data[] | select(.autoinvoke == false) | .id' <<< "$skills" | sort)
expected_hidden=$(sed -nE '/^(principle|language)-/p' <<< "$expected")
if [[ $hidden != "$expected_hidden" ]]; then
  echo "OpenCode hides these skills from the model, where it should hide exactly the principle and language skills:" >&2
  echo "${hidden:-none}" >&2
  status=1
fi
exit $status
