#!/usr/bin/env bash
# Copies each vendored skill from its upstream at the commit vendor.json records, with any README.md row for it.
# Upstream licenses the repository, not each skill, so each copy holds upstream's root LICENSE beside it.
# --check fails when a copy or its LICENSE differs from upstream; --update [<name>] first moves each record,
# or the one named, to upstream's latest commit.
set -euo pipefail
mode=${1:-copy}
only=${2:-}
case $mode in copy | --check | --update) ;; *) echo "scripts/vendor.sh: unknown mode $mode; use --check or --update [<name>]" >&2; exit 2 ;; esac
if [[ -n $only ]] && ! jq -e --arg c "$only" 'has($c)' vendor.json > /dev/null; then
  echo "scripts/vendor.sh: vendor.json has no record $only; name one of its keys" >&2
  exit 2
fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
status=0
for copy in $(jq -r 'keys[]' vendor.json); do
  [[ -n $only && $copy != "$only" ]] && continue
  record() { jq -r --arg c "$copy" ".[\$c].$1" vendor.json; }
  upstream=$(record upstream) source=$(record source) folder=$(record folder) commit=$(record commit)
  git init -q "$work/$copy"
  # Fetches only the one commit needed, so a check downloads no history.
  [[ $mode == --update ]] && want=HEAD || want=$commit
  git -C "$work/$copy" fetch -q --depth 1 "$upstream" "$want"
  git -C "$work/$copy" checkout -q FETCH_HEAD
  same() {
    diff -r -x LICENSE "$work/$copy/$source/$1" "$folder/$1" > /dev/null && cmp -s "$work/$copy/LICENSE" "$folder/$1/LICENSE"
  }
  if [[ $mode == --update ]]; then
    # Keeps the record where upstream's new commits leave every copied skill unchanged, so no empty update opens.
    changed=false
    for skill in $(record 'skills[]'); do same "$skill" || changed=true; done
    [[ $changed == false ]] && continue
    commit=$(git -C "$work/$copy" rev-parse FETCH_HEAD)
    jq --arg c "$copy" --arg h "$commit" '.[$c].commit = $h' vendor.json > "$work/vendor.json"
    mv "$work/vendor.json" vendor.json
    # The same line every time, so the update needs only the owner's merge; a rerun leaves one copy in [Unreleased].
    line="- The vendored $copy skills move to a newer upstream commit."
    if ! awk -v line="$line" '/^## \[Unreleased\]/ { u = 1; next } /^## \[/ { u = 0 } u && $0 == line { found = 1 } END { exit !found }' CHANGELOG.md; then
      awk -v line="$line" '
        /^## \[Unreleased\]/ { unreleased = 1; print; next }
        unreleased && /^### Changed$/ { print; getline; print; print line; unreleased = 0; next }
        unreleased && (/^### (Deprecated|Removed|Fixed|Security)$/ || /^## \[/) { print "### Changed\n\n" line "\n"; unreleased = 0 }
        { print }
        END { if (unreleased) print "\n### Changed\n\n" line }
      ' CHANGELOG.md > "$work/CHANGELOG.md"
      mv "$work/CHANGELOG.md" CHANGELOG.md
    fi
  fi
  for skill in $(record 'skills[]'); do
    if [[ $mode == --check ]]; then
      same "$skill" || { echo "$folder/$skill: it or its LICENSE differs from $upstream at $commit; run scripts/vendor.sh" >&2; status=1; }
    else
      rm -rf "${folder:?}/$skill"
      cp -R "$work/$copy/$source/$skill" "$folder/$skill"
      cp "$work/$copy/LICENSE" "$folder/$skill/LICENSE"
      # README.md's skills table copies the description of each skill under plugin/skills.
      # Reads the description as YAML, as scripts/check.ts does, so quotes and escapes resolve the same way.
      description=$(bun -e '
        const [, frontmatter] = (await Bun.file(Bun.argv[1]).text()).match(/^---\r?\n([\s\S]*?)\r?\n---/)
        console.log(Bun.YAML.parse(frontmatter).description)
      ' "$folder/$skill/SKILL.md")
      row="| [$skill](plugin/skills/$skill/SKILL.md) |"
      # Passes both through the environment, since awk -v would read each backslash as an escape.
      ROW=$row DESCRIPTION=$description awk 'index($0, ENVIRON["ROW"] " ") == 1 { $0 = ENVIRON["ROW"] " " ENVIRON["DESCRIPTION"] " |" } { print }' README.md > "$work/README.md"
      mv "$work/README.md" README.md
    fi
  done
done
exit $status
