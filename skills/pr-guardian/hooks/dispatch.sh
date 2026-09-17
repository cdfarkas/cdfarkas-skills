#!/usr/bin/env bash
# dispatch.sh — PostToolUse/Bash. After a successful `git push` on a feature branch,
# ask the session to dispatch ONE pr-guardian agent for that branch, or to message the
# one already watching it. Non-blocking: any failure exits 0 with no output.

set -uo pipefail

HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/pr-guardian.sh"
LOG="${PR_GUARDIAN_HOME:-$HOME/.pr-guardian}/pr-guardian.log"
[[ -r "$HELPER" ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

log() { printf '[%s] dispatch: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" 2>/dev/null >> "$LOG" || true; }

emit() {
  jq -nc --arg ctx "$1" \
    '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$ctx}}'
  exit 0
}

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
session=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)
[[ -z "$cmd" || -z "$cwd" ]] && exit 0

printf '%s' "$cmd" | grep -q 'git'  || exit 0
printf '%s' "$cmd" | grep -q 'push' || exit 0
printf '%s' "$cmd" | grep -Eq -- '--delete|--prune|--dry-run|[[:space:]]-d([[:space:]]|$)' && exit 0

resp=$(printf '%s' "$input" | jq -r '.tool_response // empty' 2>/dev/null)
printf '%s' "$resp" | grep -Eqi 'rejected|error:|failed to push|fatal:' && exit 0

branch=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
[[ -z "$branch" || "$branch" == "HEAD" ]] && exit 0
printf '%s' "$branch" | grep -Eq '^(feat|fix|chore|refactor|perf|docs|ci|test)/' || exit 0

remote=$(git -C "$cwd" remote get-url origin 2>/dev/null)
repo=$(printf '%s' "$remote" | sed -E 's|.*[:/]([^/]+/[^/]+)$|\1|; s|\.git$||')
[[ -z "$repo" ]] && exit 0
toplevel=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$cwd")

orgs=$(bash "$HELPER" config orgs --dir "$toplevel" 2>/dev/null || echo '[]')
printf '%s' "$orgs" | jq -e --arg o "${repo%%/*}" 'length == 0 or index($o) != null' >/dev/null 2>&1 || exit 0

sha=$(git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
subject=$(git -C "$cwd" log -1 --format=%s 2>/dev/null)

existing=$(bash "$HELPER" get --repo "$repo" --branch "$branch" --session "$session" 2>/dev/null)
prev_agent=$(printf '%s' "$existing" | jq -r '.agent // ""' 2>/dev/null)
prev_status=$(printf '%s' "$existing" | jq -r '.status // ""' 2>/dev/null)
prev_pr=$(printf '%s' "$existing" | jq -r '.pr // ""' 2>/dev/null)

gid=$(bash "$HELPER" register --repo "$repo" --branch "$branch" \
        --worktree "$toplevel" --session "$session" --sha "$sha" 2>/dev/null)
bash "$HELPER" prune >/dev/null 2>&1 || true

log "$repo@$branch sha=$sha gid=${gid:-?} prev_agent=${prev_agent:-none} status=${prev_status:-new}"

if [[ -n "$prev_agent" && "$prev_status" == "live" ]]; then
  IFS= read -r -d '' ctx <<CTX || true
[pr-guardian] A PR guardian is ALREADY watching ${repo} @ ${branch}${prev_pr:+ (PR #${prev_pr})}.

Its handle: **${prev_agent}**  (guardian id ${gid})

Do NOT spawn a second guardian for this branch. Tell the existing one that the branch moved, so it re-baselines instead of amending a SHA it has not read:

  SendMessage({ to: "${prev_agent}", message: "New commit pushed on ${branch} — HEAD is now ${sha} (\\"${subject}\\"). Re-read the diff and restart your cycle from the new SHA." })

If SendMessage reports that agent as gone, it died with an earlier session: dispatch a fresh pr-guardian for ${repo} @ ${branch} and re-register its handle with
  bash "${HELPER}" set --id ${gid} --agent "<new handle>"
CTX
  emit "$ctx"
fi

lost_note=""
case "$prev_status" in
  lost|orphaned) lost_note="A previous guardian (${prev_agent:-unregistered}) watched this branch in an earlier session and is gone. Replace it." ;;
esac

IFS= read -r -d '' ctx <<CTX || true
[pr-guardian] Push detected: ${repo} @ ${branch} (HEAD ${sha}). ${lost_note}

Dispatch the background PR guardian now, in this same response if nothing blocks you — the \`pr-guardian\` agent from the pr-guardian plugin:

  Agent({ subagent_type: "pr-guardian", description: "guard ${branch}", prompt: "<the brief below>" })

The brief MUST carry, verbatim (a subagent has none of this conversation's context):
  - repo: ${repo}
  - branch: ${branch}
  - worktree: ${toplevel}
  - guardian id: ${gid}
  - script: ${HELPER}
  - HEAD at dispatch: ${sha} — "${subject}"
  - your own agent handle, so it can be addressed later
  - acceptance: PR mergeable, every required check green, no unresolved review thread.

Add \`--dry-run\` to the brief to get the diagnosis and the action plan without any push (the guardian then only runs \`pr-guardian.sh plan\` and reports).

Then IMMEDIATELY record the handle the Agent tool returned, or nobody will be able to talk to it:

  bash "${HELPER}" set --id ${gid} --agent "<agent name or id returned by the Agent tool>"

Tell the user in one line that the guardian is running and how to reach it. From then on, any further commit on ${branch} goes to that guardian via SendMessage — never a second guardian.
CTX
emit "$ctx"
