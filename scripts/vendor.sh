#!/usr/bin/env bash
# Copies each vendored skill from its upstream at the commit vendor.json records, with any README.md row for it.
# Upstream licenses the repository, not each skill, so each copy holds upstream's root LICENSE beside it.
# Usage: scripts/vendor.sh [{copy | --check | --update} [<name>]], where copy is the default and a name, which follows
# a mode, limits the run to that record. --check fails when a copy or its LICENSE differs from upstream; --update also moves each record to
# upstream's latest commit where a copied skill or its LICENSE changed there.
set -euo pipefail
if (( $# > 2 )); then
  echo "scripts/vendor.sh: takes a mode and at most one name; got $*" >&2
  exit 2
fi
if (( $# == 2 )) && [[ -z $2 ]]; then
  echo "scripts/vendor.sh: the name is empty; name one of vendor.json's keys" >&2
  exit 2
fi
mode=${1-copy}
only=${2-}
case $mode in copy | --check | --update) ;; *) echo "scripts/vendor.sh: unknown mode $mode; use copy, --check or --update, each with an optional name" >&2; exit 2 ;; esac
unreadable() {
  echo "scripts/vendor.sh: cannot read $1 in vendor.json; run bun scripts/check.ts, which says what it needs" >&2
  exit 1
}
# Reads vendor.json in assignments of one command substitution each, since an assignment fails with its last command
# substitution, where a for list runs on with whatever a failed one printed:
# https://www.gnu.org/software/bash/manual/html_node/Simple-Command-Expansion.html
copies=$(jq -er 'objects | keys | join(" ")' vendor.json) || unreadable "the records"
if [[ -n $only ]] && ! jq -e --arg c "$only" 'has($c)' vendor.json > /dev/null; then
  echo "scripts/vendor.sh: vendor.json has no record $only; name one of its keys" >&2
  exit 2
fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
status=0
# Puts upstream's root LICENSE at the top of a skill folder, replacing any LICENSE or symlink there rather than writing
# through it, and stops the run where that fails, as set -e does not inside a function called left of ||:
# https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html
license() {
  rm -f "$1/LICENSE" && cp "$work/$copy/LICENSE" "$1/LICENSE" || { echo "scripts/vendor.sh: cannot put upstream's LICENSE in $1" >&2; exit 1; }
}
for copy in $copies; do
  [[ -n $only && $copy != "$only" ]] && continue
  record() { jq -er --arg c "$copy" ".[\$c].$1 | $2" vendor.json || unreadable "$1 of $copy"; }
  upstream=$(record upstream strings)
  source=$(record source strings)
  folder=$(record folder strings)
  commit=$(record commit strings)
  skills=$(record skills 'arrays | select(all(type == "string")) | join(" ")')
  git init -q "$work/$copy"
  # Fetches only the commits needed, so a run downloads no history.
  git -C "$work/$copy" fetch -q --depth 1 "$upstream" "$commit"
  moved=
  if [[ $mode == --update ]]; then
    git -C "$work/$copy" fetch -q --depth 1 "$upstream" HEAD
    latest=$(git -C "$work/$copy" rev-parse FETCH_HEAD)
    paths=(LICENSE)
    for skill in $skills; do paths+=("$source/$skill"); done
    # Moves the record only where upstream changed a copied skill or its LICENSE; a copy that only drifted is copied
    # back at its recorded commit.
    compared=0
    git -C "$work/$copy" diff --quiet "$commit" "$latest" -- "${paths[@]}" || compared=$?
    case $compared in
      0) ;;
      1) moved=$latest ;;
      *) echo "scripts/vendor.sh: git could not compare $upstream at $commit with $latest; run it again" >&2; exit 1 ;;
    esac
  fi
  git -C "$work/$copy" checkout -q "${moved:-$commit}"
  # Refuses a symlink on the way to or inside what it copies, since copying one would read or write outside the fetched
  # tree, and a skill upstream no longer holds.
  at="$upstream at ${moved:-$commit}"
  copied=("$work/$copy/LICENSE")
  for skill in $skills; do
    path=$work/$copy
    for part in ${source//\// } "$skill"; do
      path+=/$part
      [[ -L $path ]] && { echo "scripts/vendor.sh: $at holds a symlink at ${path#"$work/$copy/"}, which it does not copy; ask upstream to replace it with the file, or keep the copy at a commit without it" >&2; exit 1; }
    done
    if [[ ! -d $path ]]; then
      if [[ -n $moved ]]; then fix="upstream dropped it: remove $skill from vendor.json's skills, delete $folder/$skill and the changelog's mention of it, then run bun run check, which names each list it checks that still holds it"; else fix="check this record's commit and skills in vendor.json"; fi
      echo "scripts/vendor.sh: $at has no $source/$skill; $fix" >&2
      exit 1
    fi
    copied+=("$path")
  done
  if [[ ! -e $work/$copy/LICENSE && ! -L $work/$copy/LICENSE ]]; then
    if [[ -n $moved ]]; then fix="keep the copy at its recorded commit until upstream restores it"; else fix="set this record's commit in vendor.json to one that has it"; fi
    echo "scripts/vendor.sh: $at has no root LICENSE, which each copy holds beside it; $fix" >&2
    exit 1
  fi
  link=$(find "${copied[@]}" -type l -print -quit)
  if [[ -n $link ]]; then
    echo "scripts/vendor.sh: $at holds a symlink at ${link#"$work/$copy/"}, which it does not copy; ask upstream to replace it with the file, or keep the copy at a commit without it" >&2
    exit 1
  fi
  # Compares a copy with what copying it produces: upstream's skill, with upstream's root LICENSE on top.
  same() {
    license "$work/$copy/$source/$1"
    diff -r "$work/$copy/$source/$1" "$folder/$1" > /dev/null
  }
  for skill in $skills; do
    if [[ $mode == --check ]]; then
      same "$skill" || { echo "$folder/$skill: it or its LICENSE differs from $upstream at $commit; run scripts/vendor.sh" >&2; status=1; }
    else
      rm -rf "${folder:?}/$skill"
      cp -R "$work/$copy/$source/$skill" "$folder/$skill"
      license "$folder/$skill"
      # README.md's skills table copies the description of each skill under plugin/skills.
      # Reads the description as YAML, as scripts/check.ts does, so quotes and escapes resolve the same way.
      description=$(bun -e '
        const [, frontmatter] = (await Bun.file(Bun.argv[1]).text()).match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/)
        console.log(Bun.YAML.parse(frontmatter).description)
      ' "$folder/$skill/SKILL.md")
      row="| [$skill](plugin/skills/$skill/SKILL.md) |"
      # Passes both through the environment, since awk -v would read each backslash as an escape.
      ROW=$row DESCRIPTION=$description awk 'index($0, ENVIRON["ROW"] " ") == 1 { $0 = ENVIRON["ROW"] " " ENVIRON["DESCRIPTION"] " |" } { print }' README.md > "$work/README.md"
      mv "$work/README.md" README.md
    fi
  done
  # Moves the record last, so a run stopped at any line leaves it at the old commit, and a rerun repeats the update.
  if [[ -n $moved ]]; then
    # The same line every time, so the update needs only the owner's merge; a rerun leaves one copy in [Unreleased].
    line="- Each skill vendored from $copy moves to a newer upstream commit."
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
    jq --arg c "$copy" --arg h "$moved" '.[$c].commit = $h' vendor.json > "$work/vendor.json"
    mv "$work/vendor.json" vendor.json
  fi
done
exit $status
