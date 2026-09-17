#!/usr/bin/env bash
# session-end.sh — SessionEnd. A pr-guardian dies with its session, possibly mid-write:
# release its lock and mark its entry orphaned so adopt.sh surfaces it next session.
# Only guardians of THIS session are touched. Never blocks, never fails loudly.

set -uo pipefail

HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/pr-guardian.sh"
LOG="${PR_GUARDIAN_HOME:-$HOME/.pr-guardian}/pr-guardian.log"

log() { printf '[%s] session-end: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" 2>/dev/null >> "$LOG" || true; }

[[ -r "$HELPER" ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)
session=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)
[[ -z "$session" ]] && exit 0

mine=$(bash "$HELPER" list --json 2>/dev/null \
  | jq -r --arg s "$session" '.[] | select(.status == "live" and .session_id == $s)
      | [.id, .repo, .branch, .pr] | @tsv' 2>/dev/null)
[[ -z "$mine" ]] && exit 0

count=0
last=""
while IFS=$'\t' read -r id repo branch pr; do
  [[ -z "$repo" || -z "$branch" ]] && continue

  if bash "$HELPER" locked --repo "$repo" --branch "$branch" >/dev/null 2>&1; then
    bash "$HELPER" release --repo "$repo" --branch "$branch" >/dev/null 2>&1 || true
    log "released orphaned lock on $repo@$branch"
  fi

  bash "$HELPER" set --id "$id" --orphan \
    --note "guardian lost when session $session ended${pr:+ (PR #$pr)} — PR not confirmed green, awaiting adoption" >/dev/null 2>&1 || true

  count=$((count + 1))
  last="$repo @ $branch"
  log "orphaned $repo@$branch (guardian $id)"
done <<< "$mine"

(( count == 0 )) && exit 0

if command -v osascript >/dev/null 2>&1; then
  if (( count == 1 )); then
    msg="$last — PR not confirmed green"
  else
    msg="$count branches unwatched, incl. $last"
  fi
  osascript -e "display notification \"${msg//\"/}\" with title \"PR guardian lost\" subtitle \"Re-adopted at next session start\"" \
    >/dev/null 2>&1 || true
fi
exit 0
