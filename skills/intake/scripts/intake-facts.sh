#!/usr/bin/env bash
#
# intake-facts: print the facts an intake starts from, one per line: git state, project
# instruction files, package manager, package.json scripts, installed dependencies, and the
# local agents the skill's subagents can use. Read-only; no network unless --fetch.

set -u
export LC_ALL=C

usage() {
  cat <<USAGE
Usage: $(basename "${0}") [--fetch]

Prints one fact per line about the project in the current directory.

  --fetch      git fetch the upstream's remote before counting ahead/behind (network)
  -h, --help   this help
USAGE
}

FETCH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --fetch) FETCH=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

fact() { printf '%s: %s\n' "$1" "$2"; }

git_facts() {
  local cdup branch up track remote out when
  if ! command -v git >/dev/null 2>&1; then
    fact root "$(pwd)"
    fact git "not installed"
    return
  fi
  if [ "$(git rev-parse --is-inside-work-tree 2>&1)" != true ]; then
    fact root "$(pwd)"
    fact git "not a git repository"
    return
  fi
  cdup=$(git rev-parse --show-cdup)
  [ -z "$cdup" ] || cd "$cdup" || exit 1
  fact root "$(pwd)"
  branch=$(git symbolic-ref --short -q HEAD) || branch=""
  if [ -z "$branch" ]; then
    fact branch "detached at $(git rev-parse --short HEAD)"
    fact upstream "none"
  else
    fact branch "$branch"
    up=$(git for-each-ref --format='%(upstream:short)' "refs/heads/$branch")
    if [ -z "$up" ]; then
      fact upstream "none"
    else
      when="as of the last fetch"
      if [ "$FETCH" = 1 ]; then
        remote=$(git config "branch.$branch.remote")
        if out=$(git fetch --quiet "$remote" 2>&1); then
          when="fetched now"
        else
          when="fetch failed: $(printf '%s\n' "$out" | tail -n 1)"
        fi
      fi
      track=$(git for-each-ref --format='%(upstream:track,nobracket)' "refs/heads/$branch")
      case "$track" in
        "") track="ahead 0, behind 0" ;;
        gone|ahead*behind*) ;;
        ahead*) track="$track, behind 0" ;;
        behind*) track="ahead 0, $track" ;;
      esac
      fact upstream "$up, $track ($when)"
    fi
  fi
  fact uncommitted "$(git status --porcelain --untracked-files=all | awk 'END { print NR }') files (staged, unstaged and untracked)"
}

first_file() {
  local f
  for f in "$@"; do
    if [ -f "$f" ]; then printf '%s' "$f"; return 0; fi
  done
  return 1
}

instruction_facts() {
  local found="" f d n adr="none"
  for f in CLAUDE.md .claude/CLAUDE.md AGENTS.md; do
    if [ -f "$f" ]; then found="${found:+$found, }$f"; fi
  done
  if f=$(first_file README.md README README.rst README.txt); then found="${found:+$found, }$f"; fi
  if f=$(first_file CONTRIBUTING.md .github/CONTRIBUTING.md docs/CONTRIBUTING.md); then found="${found:+$found, }$f"; fi
  fact instructions "${found:-none}"
  for d in docs/adr docs/adrs docs/decisions doc/adr adr adrs decisions docs/architecture/decisions; do
    if [ -d "$d" ]; then
      n=$(find "$d" -type f -name '*.md' | awk 'END { print NR }')
      adr="$d ($n files)"
      break
    fi
  done
  fact adr "$adr"
}

package_facts() {
  local found="" pair out
  for pair in pnpm-lock.yaml:pnpm yarn.lock:yarn package-lock.json:npm npm-shrinkwrap.json:npm \
      bun.lock:bun bun.lockb:bun go.sum:go Cargo.lock:cargo uv.lock:uv poetry.lock:poetry \
      Gemfile.lock:bundler composer.lock:composer; do
    if [ -f "${pair%%:*}" ]; then found="${found:+$found, }${pair##*:} (${pair%%:*})"; fi
  done
  if [ -n "$found" ]; then
    fact "package manager" "$found"
  elif [ -f package.json ]; then
    fact "package manager" "unknown (package.json, no lockfile)"
  else
    fact "package manager" "none (no lockfile, no package.json)"
  fi
  [ -f package.json ] || return 0
  if ! command -v node >/dev/null 2>&1; then
    fact scripts "unknown (node not found)"
  elif out=$(node -e '
      const s = JSON.parse(require("fs").readFileSync("package.json", "utf8")).scripts || {};
      for (const k of ["test", "lint", "typecheck", "build"]) console.log(`script ${k}: ${s[k] || "none"}`);
    ' 2>&1); then
    printf '%s\n' "$out"
  else
    fact scripts "unreadable (package.json does not parse)"
  fi
  if [ -d node_modules ] || [ -f .pnp.cjs ]; then
    fact dependencies "installed (node_modules present)"
  else
    fact dependencies "not installed (no node_modules)"
  fi
}

has_agent() {
  local f
  [ -d "$1" ] || return 1
  for f in "$1"/*.md; do
    if [ -f "$f" ] && grep -q -E "^name:[[:space:]]*$2[[:space:]]*\$" "$f"; then return 0; fi
  done
  return 1
}

agent_facts() {
  local name
  for name in devils-advocate finding-verifier; do
    if has_agent .claude/agents "$name"; then
      fact "agent $name" "yes (.claude/agents)"
    elif has_agent "${HOME:-}/.claude/agents" "$name"; then
      fact "agent $name" "yes (~/.claude/agents)"
    else
      fact "agent $name" "no (fallback: general-purpose)"
    fi
  done
}

git_facts
instruction_facts
package_facts
agent_facts
