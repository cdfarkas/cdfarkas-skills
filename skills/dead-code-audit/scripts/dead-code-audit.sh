#!/usr/bin/env bash
#
# dead-code-audit: run Knip zero-install on a JavaScript/TypeScript repo and shape
# its JSON into categorized findings (unused files, exports, exported types, unused
# dependencies, unlisted/undeclared dependencies) plus a before/after score
# (removable lines of code and the unused-dependency count).
#
# Read-only: it runs Knip and reads the reported files, nothing else. It deletes
# nothing. Every line it prints is a CANDIDATE — the caller applies the guardrails
# in SKILL.md before removing anything.

set -euo pipefail

_TARGET="."
_RUNNER=""

usage() {
  cat <<USAGE
Audits a JavaScript/TypeScript repo for dead code with Knip, zero-install.

Usage: $(basename "${0}") [<dir>] [--runner npx|pnpm|yarn]

  <dir>        repo root to audit (default: current directory)
  --runner     package runner for the zero-install Knip (default: detected from the lockfile)
  -h, --help   this help
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --runner) _RUNNER="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --*) usage >&2; echo "unknown flag: $1" >&2; exit 2 ;;
    *) _TARGET="$1"; shift ;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "jq is required but not found" >&2; exit 1; }
[ -d "$_TARGET" ] || { echo "not a directory: $_TARGET" >&2; exit 1; }
cd "$_TARGET"

# Pick the Knip runner from the lockfile unless the caller forced one.
if [ -z "$_RUNNER" ]; then
  if [ -f pnpm-lock.yaml ]; then _RUNNER="pnpm"
  elif [ -f yarn.lock ]; then _RUNNER="yarn"
  else _RUNNER="npx"; fi
fi
case "$_RUNNER" in
  npx)  _KNIP="npx --yes knip" ;;
  pnpm) _KNIP="pnpm dlx knip" ;;
  yarn) _KNIP="yarn dlx knip" ;;
  *) echo "unknown runner: $_RUNNER (npx|pnpm|yarn)" >&2; exit 2 ;;
esac

_DEFAULTED=""
_HAS_CFG=""
# Test each candidate: `ls a b c` exits non-zero when any arg is missing, so it
# mislabels a repo that has only knip.json as having no config.
for _f in knip.json knip.jsonc knip.ts knip.js .kniprc .kniprc.json; do
  [ -e "$_f" ] && { _HAS_CFG=1; break; }
done
if [ -z "$_HAS_CFG" ] && ! grep -q '"knip"' package.json 2>/dev/null; then
  _DEFAULTED=" · no Knip config, using Knip defaults"
fi

# --no-exit-code stops an issues-found exit tripping set -e; a config error can still exit
# non-zero while emitting a full report, so gate on JSON presence/parseability, not exit code.
_ERR="$(mktemp)"
trap 'rm -f "$_ERR"' EXIT
_JSON="$($_KNIP --reporter json --no-exit-code 2>"$_ERR" || true)"
if [ -z "$_JSON" ]; then
  tail -n 1 "$_ERR" >&2 || true
  echo "knip failed to run via '$_RUNNER' (is Node installed?)" >&2
  exit 1
fi
printf '%s' "$_JSON" | jq empty >/dev/null 2>&1 || {
  echo "knip produced no parseable JSON (runner: $_RUNNER)" >&2
  exit 1
}

# tr -d '\r': the Windows jq build terminates lines with CRLF; strip CR so paths match on disk.
_q() { printf '%s' "$_JSON" | jq -r "$1" | tr -d '\r'; }

_FILES="$(_q '.issues[]? | .files[]? | .name')"
_EXPORTS="$(_q '.issues[]? | . as $i | (.exports // [])[] | "\($i.file):\(.line // "?")\t\(.name)"')"
_TYPES="$(_q '.issues[]? | . as $i | (.types // [])[] | "\($i.file):\(.line // "?")\t\(.name)"')"
_DEPS="$(_q '[.issues[]? | (.dependencies // [], .devDependencies // [], .optionalPeerDependencies // [])[] | .name] | unique | .[]')"
_UNLISTED="$(_q '[.issues[]? | (.unlisted // [])[] | .name] | unique | .[]')"

_cnt() { [ -z "$1" ] && echo 0 || printf '%s\n' "$1" | grep -c .; }
_nfiles=$(_cnt "$_FILES"); _nexp=$(_cnt "$_EXPORTS"); _ntypes=$(_cnt "$_TYPES")
_ndeps=$(_cnt "$_DEPS"); _nunlisted=$(_cnt "$_UNLISTED")

_LOC=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  [ -f "$f" ] || continue
  n=$(wc -l <"$f" 2>/dev/null | tr -d ' ')
  _LOC=$((_LOC + ${n:-0}))
done <<EOF
$_FILES
EOF

section() { # title, count, lines
  printf '\n%s (%s)\n' "$1" "$2"
  if [ "$2" -eq 0 ]; then printf -- '- (none)\n'; else printf '%s\n' "$3" | sed 's/^/- /'; fi
}

printf 'Dead-code audit · %s · %s · Knip%s\n' "$(basename "$(pwd)")" "$(date +%Y-%m-%d)" "$_DEFAULTED"
section "Unused files" "$_nfiles" "$_FILES"
section "Unused exports" "$_nexp" "$_EXPORTS"
section "Unused exported types" "$_ntypes" "$_TYPES"
section "Unused dependencies" "$_ndeps" "$_DEPS"
section "Unlisted / undeclared dependencies" "$_nunlisted" "$_UNLISTED"

printf '\nBefore/after score (candidates — verify against the guardrails before removing)\n'
printf -- '- removable lines of code: %s across %s unused file(s)\n' "$_LOC" "$_nfiles"
printf -- '- unused dependencies: %s\n' "$_ndeps"
