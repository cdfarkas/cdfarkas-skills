#!/usr/bin/env bash
# adopt.sh — SessionStart. Runs the doctor (one warning line on FAIL, never blocks),
# then surfaces the orphaned guardians whose PR still needs work so the session can
# re-dispatch them. Bounded to the 3 most recent orphans, one short `gh` call each.

set -uo pipefail

HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/pr-guardian.sh"
LOG="${PR_GUARDIAN_HOME:-$HOME/.pr-guardian}/pr-guardian.log"
MAX=3
STALE_MIN=45

quiet_exit() { echo '{}'; exit 0; }
log() { printf '[%s] adopt: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" 2>/dev/null >> "$LOG" || true; }
iso_utc() { date -u -r "$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null; }
with_timeout() {
  if command -v timeout >/dev/null 2>&1; then timeout "$@"
  elif command -v gtimeout >/dev/null 2>&1; then gtimeout "$@"
  else shift; "$@"; fi
}
emit() { printf '%s' "$1" | jq -Rs '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: .}}'; exit 0; }

[[ -r "$HELPER" ]] || quiet_exit
command -v jq >/dev/null 2>&1 || quiet_exit

input=$(cat)
session=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)

warning=""
fail=$(bash "$HELPER" doctor 2>&1 | grep -m1 '^FAIL' || true)
if [[ -n "$fail" ]]; then
  warning="[pr-guardian] prerequisite missing — ${fail#FAIL  }. No guardian will be dispatched until \`bash \"${HELPER}\" doctor\` passes."
  log "doctor: $fail"
fi

command -v gh >/dev/null 2>&1 || { [[ -n "$warning" ]] && emit "$warning"; quiet_exit; }
bash "$HELPER" prune >/dev/null 2>&1 || true

stale_before=$(iso_utc $(( $(date +%s) - STALE_MIN * 60 ))) || stale_before=""
orphans=$(bash "$HELPER" list --json 2>/dev/null \
  | jq -r --argjson max "$MAX" --arg me "$session" --arg stale "$stale_before" '
      [ .[]
        | select(.session_id != $me)
        | select(.status == "orphaned" or ($stale != "" and .updated_at < $stale))
      ]
      | sort_by(.updated_at) | reverse | .[:$max]
      | .[] | [.id, .repo, .branch, .worktree, .pr, .last_sha] | @tsv' 2>/dev/null)
[[ -z "$orphans" ]] && { [[ -n "$warning" ]] && emit "$warning"; quiet_exit; }

blocks=""
while IFS=$'\t' read -r id repo branch worktree pr sha; do
  [[ -z "$repo" || -z "$branch" ]] && continue

  state=$(with_timeout 10 gh pr view "${pr:-$branch}" --repo "$repo" \
            --json state,mergeable,reviewDecision,statusCheckRollup 2>/dev/null) || continue
  [[ -z "$state" ]] && continue

  pr_state=$(printf '%s' "$state" | jq -r '.state // ""')
  if [[ "$pr_state" == "MERGED" || "$pr_state" == "CLOSED" ]]; then
    bash "$HELPER" done --repo "$repo" --branch "$branch" >/dev/null 2>&1 || true
    log "$repo@$branch $pr_state — closed out, not adopted"
    continue
  fi

  failing=$(printf '%s' "$state" | jq -r '
    [(.statusCheckRollup // [])[]
     | select((.conclusion // "") | test("FAILURE|TIMED_OUT|CANCELLED|ACTION_REQUIRED"))
     | .name // .context] | join(", ")')
  pending=$(printf '%s' "$state" | jq -r '
    [(.statusCheckRollup // [])[]
     | select((.status // "") == "IN_PROGRESS" or (.status // "") == "QUEUED")] | length')
  mergeable=$(printf '%s' "$state" | jq -r '.mergeable // "UNKNOWN"')
  review=$(printf '%s' "$state" | jq -r '.reviewDecision // ""')

  if [[ -z "$failing" && "$pending" == "0" && "$mergeable" == "MERGEABLE" ]]; then
    bash "$HELPER" set --id "$id" --note "green at session start — no adoption needed" >/dev/null 2>&1 || true
    log "$repo@$branch green — not adopted"
    continue
  fi

  reason=""
  [[ -n "$failing" ]] && reason="checks failing: ${failing}"
  [[ "$mergeable" == "CONFLICTING" ]] && reason="${reason:+$reason; }CONFLICTING — needs a rebase"
  [[ "$pending" != "0" ]] && reason="${reason:+$reason; }${pending} check(s) still running"
  [[ "$review" == "CHANGES_REQUESTED" ]] && reason="${reason:+$reason; }review requested changes"

  bash "$HELPER" release --repo "$repo" --branch "$branch" >/dev/null 2>&1 || true

  blocks="${blocks}
- **${repo} @ ${branch}**${pr:+ (PR #${pr})} — ${reason:-state unclear}
  worktree: \`${worktree}\` · guardian id \`${id}\` · last known HEAD \`${sha:-?}\`"
  log "$repo@$branch orphan to adopt — $reason"
done <<< "$orphans"

[[ -z "$blocks" ]] && { [[ -n "$warning" ]] && emit "$warning"; quiet_exit; }

ctx="${warning:+$warning

}# Orphaned PR guardians (adopt these)

The guardian watching each branch below died with its session and the PR is not done. Re-dispatch one \`pr-guardian\` agent per branch (from the pr-guardian plugin), passing repo / branch / worktree / guardian id verbatim — add \`--dry-run\` to the brief for the diagnosis and action plan without any push — then record the new handle:

\`\`\`
bash \"${HELPER}\" set --id <guardian id> --agent \"<handle returned by the Agent tool>\"
\`\`\`
${blocks}

Adopt them when the user's first request leaves room; if it doesn't, say in one line that they are waiting rather than dropping them silently. Their write locks have already been released."

emit "$ctx"
