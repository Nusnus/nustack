#!/usr/bin/env bash
# Copies each vendored skill from its upstream at the commit vendor.json records, with any README.md row for it.
# Upstream licenses the repository, not each skill, so each copy holds upstream's root LICENSE beside it.
# Usage: scripts/vendor.sh [{copy | --check | --update} [<name>]], where copy is the default and a name, which follows
# a mode, limits the run to that record. --check fails when a copy or its LICENSE differs from upstream; --update also
# moves each record to upstream's latest commit where a copied skill or its LICENSE changed there.
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
# The shell gives a status of 126 or 127 to a tool it cannot run, with a message, and one over 128 to a tool a signal
# kills, which a command substitution can leave with no message, so this says that one failed:
# https://www.gnu.org/software/bash/manual/html_node/Exit-Status.html
trap 'failure=$?; (( failure <= 128 )) || echo "scripts/vendor.sh: a tool it called failed with status $failure" >&2' ERR
# Called with the status jq failed with. 1, 2, 4 and 5 are jq's for a vendor.json it cannot open or that does not hold
# what jq asked of it. 3 is jq's for a program it cannot compile, and no other status under 126 is one of jq's, so
# each stops the run as a failure of jq's own. A higher one is the shell's, and goes back to the shell, which stops
# the run on it. jq's manual gives each of its statuses but 5, which its source names JQ_ERROR_UNKNOWN:
# https://jqlang.org/manual/#invoking-jq
# https://github.com/jqlang/jq/blob/jq-1.8.1/src/main.c
unreadable() {
  (( $1 < 126 )) || return "$1"
  (( $1 != 3 && $1 <= 5 )) || failed jq "$1"
  echo "scripts/vendor.sh: cannot read $2 in vendor.json; run bun scripts/check.ts, which says what it needs" >&2
  exit 1
}
# Asks a command a question it answers with its status: returns its 0 or 1, and stops the run on a higher status, a
# failure that a condition would read as a no, since set -e stops for no command a condition runs:
# https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html
ask() {
  answer=0
  "$@" || answer=$?
  (( answer <= 1 )) || failed "$1" "$answer"
  return "$answer"
}
# Stops the run for a tool whose status is no answer. The tool or the shell has said why above, unless a signal
# killed the tool.
failed() {
  echo "scripts/vendor.sh: $1 failed with status $2" >&2
  exit 1
}
# Reads each list it loops over in an assignment of one command substitution, since an assignment fails with its last
# command substitution, where a for list runs on with whatever a failed one printed:
# https://www.gnu.org/software/bash/manual/html_node/Simple-Command-Expansion.html
copies=$(jq -er 'objects | keys | join(" ")' vendor.json) || unreadable $? "the records"
if [[ -n $only ]] && ! ask jq -e --arg c "$only" 'has($c)' vendor.json > /dev/null; then
  echo "scripts/vendor.sh: vendor.json has no record $only; name one of its keys" >&2
  exit 2
fi
# Git exports its repository variables to a command it runs, as GIT_INDEX_FILE to a commit hook and GIT_DIR to a hook
# or rebase --exec in a linked worktree, which would point the Git commands below that work on the fetched repository
# at the caller's. Keeps the two that hold the settings the caller gave Git, such as a URL rewrite:
# https://git-scm.com/docs/githooks#_description
repository_variables=$(git rev-parse --local-env-vars)
for variable in $repository_variables; do
  [[ $variable == GIT_CONFIG_PARAMETERS || $variable == GIT_CONFIG_COUNT ]] || unset "$variable"
done
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
status=0
for copy in $copies; do
  [[ -n $only && $copy != "$only" ]] && continue
  record() { jq -er --arg c "$copy" ".[\$c].$1 | $2" vendor.json || unreadable $? "$1 of $copy"; }
  upstream=$(record upstream strings)
  source=$(record source strings)
  folder=$(record folder strings)
  commit=$(record commit strings)
  skills=$(record skills 'arrays | select(all(type == "string")) | join(" ")')
  # A folder the record does not name, so no record's name meets a scratch file of this script.
  fetched=$(mktemp -d "$work/fetched.XXXXXX")
  # From an empty template, so the repository holds nothing of the caller's own template, such as a hook, or a link
  # where its attributes file goes: https://git-scm.com/docs/git-init#_template_directory
  mkdir -p "$work/template"
  git init -q --template="$work/template" "$fetched"
  # Unsets text for every path, so a checkout converts no line ending and each copy holds its commit's, whatever a
  # Git setting or another attributes file asks for: this attributes file outranks every other, and sits in a folder
  # the empty template leaves out.
  # https://git-scm.com/docs/gitattributes#_description
  # https://git-scm.com/docs/gitattributes#_text
  mkdir -p "$fetched/.git/info"
  echo '* -text' > "$fetched/.git/info/attributes"
  # Fetches only the commits needed, so a run downloads no history, and starts none of Git's maintenance, which
  # would still write into the folder while the exit trap removes it:
  # https://git-scm.com/docs/git-fetch#Documentation/git-fetch.txt---no-auto-maintenance
  git -C "$fetched" fetch -q --no-auto-maintenance --depth 1 "$upstream" "$commit"
  moved=
  if [[ $mode == --update ]]; then
    git -C "$fetched" fetch -q --no-auto-maintenance --depth 1 "$upstream" HEAD
    latest=$(git -C "$fetched" rev-parse FETCH_HEAD)
    paths=(LICENSE)
    for skill in $skills; do paths+=("$source/$skill"); done
    # Moves the record only where upstream changed a copied skill or its LICENSE; a copy that only drifted is copied
    # back at its recorded commit. Compares the bytes, whatever diff program or text conversion the caller's settings
    # name:
    # https://git-scm.com/docs/git-diff#Documentation/git-diff.txt---no-ext-diff
    ask git -C "$fetched" diff --quiet --no-ext-diff --no-textconv "$commit" "$latest" -- "${paths[@]}" || moved=$latest
  fi
  git -C "$fetched" checkout -q "${moved:-$commit}"
  # Refuses a symlink on the way to or inside what it copies, since copying one would read or write outside the fetched
  # tree, and a skill upstream no longer holds.
  at="$upstream at ${moved:-$commit}"
  refuse_symlink() {
    echo "scripts/vendor.sh: $at holds a symlink at ${1#"$fetched/"}, which it does not copy; ask upstream to replace it with the file, or keep the copy at a commit without it" >&2
    exit 1
  }
  copied=("$fetched/LICENSE")
  for skill in $skills; do
    path=$fetched
    for part in ${source//\// } "$skill"; do
      path+=/$part
      [[ -L $path ]] && refuse_symlink "$path"
    done
    if [[ ! -d $path ]]; then
      # Upstream moved or dropped a folder the recorded commit holds. One that commit lacks is the record's error, or,
      # once the record's source follows a folder upstream moved, a skill upstream dropped in that move.
      # Asks Git for the folder by its object name, which is no pathspec for the caller's pathspec variables to
      # change, and in a batch, which prints "<object> missing" for a name the commit lacks where git cat-file -t fails:
      # https://git-scm.com/docs/git#Documentation/git.txt-GITGLOBPATHSPECS
      # https://git-scm.com/docs/git-cat-file#_batch_output
      held=$(git -C "$fetched" cat-file --batch-check='%(objecttype)' <<< "$commit:${path#"$fetched/"}")
      dropped="remove $skill from vendor.json's skills and delete $folder/$skill/, then run bun run check, which names each list it checks that still holds it"
      if [[ $held == tree ]]; then
        fix="upstream moved or dropped it: if upstream moved the folder that holds this record's skills, set the record's source in vendor.json to that folder; if it moved only some of them, move those to a record of their own whose source is the folder that holds them now; then run scripts/vendor.sh --update again; if dropped, $dropped"
      else
        fix="check this record's commit, source and skills in vendor.json${moved:+; if upstream dropped the skill, $dropped}"
      fi
      echo "scripts/vendor.sh: $at has no $source/$skill/; $fix" >&2
      exit 1
    fi
    copied+=("$path")
  done
  if [[ ! -e $fetched/LICENSE && ! -L $fetched/LICENSE ]]; then
    held=$(git -C "$fetched" cat-file --batch-check='%(objecttype)' <<< "$commit:LICENSE")
    if [[ $held != *' missing' ]]; then fix="keep the copy at its recorded commit until upstream restores it"; else fix="set this record's commit in vendor.json to one that has it"; fi
    echo "scripts/vendor.sh: $at has no root LICENSE, which each copy holds beside it; $fix" >&2
    exit 1
  fi
  link=$(find "${copied[@]}" -type l -print -quit)
  [[ -n $link ]] && refuse_symlink "$link"
  # README.md's skills table copies the description of each skill under plugin/skills/, on one line. Writes the rows
  # into a scratch copy before it copies anything, and puts it in place after the copies, so a stop on a skill writes
  # nothing of its record. Reads the description as YAML, as scripts/check.ts does, so quotes and escapes resolve the
  # same way.
  if [[ $mode != --check && $folder -ef plugin/skills ]]; then
    cp README.md "$work/README.md"
    for skill in $skills; do
      row="| [$skill](plugin/skills/$skill/SKILL.md) |"
      # Prints the skill's row, and nothing where upstream holds no such file, or one plugin/opencode.ts refuses, as
      # one that is not UTF-8 or whose frontmatter is not YAML with a name and a description, or where the description
      # holds a line break or a NUL, which a row cannot hold and a shell variable drops.
      described=$(bun -e '
        const file = Bun.file(Bun.argv[1])
        const bytes = (await file.exists()) ? await file.bytes() : new Uint8Array()
        // Read outside the try, so a Bun older than its YAML parser fails as itself, not as a file upstream lacks:
        // https://bun.sh/blog/bun-v1.2.21
        const { parse } = Bun.YAML
        let fields
        try {
          const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes)
          const [, frontmatter] = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/) ?? []
          fields = frontmatter && parse(frontmatter)
        } catch {}
        const { name, description } = Object(fields)
        if (typeof name === "string" && typeof description === "string" && !/[\r\n\0]/.test(description))
          console.log(`${Bun.argv[2]} ${description} |`)
      ' "$fetched/$source/$skill/SKILL.md" "$row")
      if [[ -z $described ]]; then
        echo "scripts/vendor.sh: $at holds no UTF-8 $source/$skill/SKILL.md whose YAML frontmatter holds a name and a one-line description with no NUL; ask upstream for one, or keep the copy at a commit that has it" >&2
        exit 1
      fi
      # Passes both through the environment, since awk -v would read each backslash as an escape:
      # https://pubs.opengroup.org/onlinepubs/9699919799/utilities/awk.html
      ROW=$row DESCRIBED=$described awk 'index($0, ENVIRON["ROW"] " ") == 1 { $0 = ENVIRON["DESCRIBED"] } { print }' "$work/README.md" > "$work/README.next"
      mv "$work/README.next" "$work/README.md"
    done
  fi
  # Compares a copy with what copying it produces: upstream's skill, with upstream's root LICENSE on top.
  compare() {
    license "$fetched/$source/$1"
    # diff exits with 2 where it cannot read a file, as in a copy that is missing or holds a symlink to nothing, and
    # such a copy differs too. A higher status is no answer of diff's, as the shell's for a diff it could not run or a
    # signal killed:
    # https://www.gnu.org/software/diffutils/manual/html_node/Invoking-diff.html
    difference=0
    diff -r "$fetched/$source/$1" "$folder/$1" > /dev/null || difference=$?
    (( difference )) || return 0
    (( difference <= 2 )) || failed diff "$difference"
    echo "$folder/$1: it or its LICENSE differs from $upstream at $commit; run scripts/vendor.sh" >&2
    status=1
  }
  # Puts upstream's root LICENSE at the top of a skill folder, replacing any LICENSE or symlink there rather than
  # writing through it.
  license() {
    rm -f "$1/LICENSE"
    cp "$fetched/LICENSE" "$1/LICENSE"
  }
  for skill in $skills; do
    if [[ $mode == --check ]]; then
      compare "$skill"
    else
      rm -rf "${folder:?}/$skill"
      cp -R "$fetched/$source/$skill" "$folder/$skill"
      license "$folder/$skill"
    fi
  done
  [[ ! -e $work/README.md ]] || mv "$work/README.md" README.md
  # Moves the record last, so a run stopped at any line leaves it at the old commit, and a rerun repeats the update.
  if [[ -n $moved ]]; then
    # The same line every time, so the update needs only the owner's merge; a rerun leaves one copy in [Unreleased].
    line="- Each skill vendored from $copy moves to a newer upstream commit."
    if ! ask awk -v line="$line" '/^## \[Unreleased\]/ { u = 1; next } /^## \[/ { u = 0 } u && $0 == line { found = 1 } END { exit !found }' CHANGELOG.md; then
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
