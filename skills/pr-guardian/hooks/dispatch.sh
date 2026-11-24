#!/usr/bin/env bash
# dispatch.sh — PostToolUse/Bash. After a successful `git push` on a feature branch,
# ask the session to dispatch ONE pr-guardian agent for that branch, or to message the
# one already watching it. Non-blocking: any failure exits 0 with no output.

set -uo pipefail

HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/pr-guardian.sh"
LOG="${PR_GUARDIAN_HOME:-$HOME/.pr-guardian}/pr-guardian.log"
PUSH_MAX_AGE=600
[[ -r "$HELPER" && -r "${HELPER%/*}/git-target.sh" ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0
# shellcheck source=../scripts/git-target.sh
. "${HELPER%/*}/git-target.sh"

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

gt_is_git_verb "$cmd" push || exit 0
printf '%s' "$cmd" | grep -Eq -- '--delete|--prune|--dry-run|[[:space:]]-d([[:space:]]|$)' && exit 0

resp=$(printf '%s' "$input" | jq -r '.tool_response // empty' 2>/dev/null)
printf '%s' "$resp" | grep -Eqi 'rejected|error:|failed to push|fatal:' && exit 0

# candidate <dir> — take its repository when a push moved the remote-tracking ref of its branch
# to HEAD less than PUSH_MAX_AGE ago and HEAD is not registered yet. A second one: silence.
toplevel=""
candidate() {
  local top b head pushed remote r orgs prefixes entry last
  top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 0
  [[ "$top" == "$toplevel" ]] && return 0
  b=$(git -C "$top" symbolic-ref -q --short HEAD 2>/dev/null) || return 0
  head=$(git -C "$top" rev-parse -q --verify HEAD 2>/dev/null) || return 0
  [[ "$(git -C "$top" symbolic-ref -q refs/remotes/origin/HEAD 2>/dev/null)" == "refs/remotes/origin/$b" ]] && return 0
  pushed=$(git -C "$top" for-each-ref --format='%(refname)' "refs/remotes/*/$b" 2>/dev/null | while IFS= read -r ref; do
    git -C "$top" log -g -1 --date=unix --format='%H %gd %gs' "$ref" -- 2>/dev/null
  done | sed -nE "s/^$head .*@\{([0-9]+)\} update by push.*/\1/p" | sort -n | tail -1)
  [[ -n "$pushed" ]] && (( $(date +%s) - pushed < PUSH_MAX_AGE )) || return 0

  remote=$(git -C "$top" remote get-url origin 2>/dev/null)
  r=$(printf '%s' "$remote" | sed -E 's|.*[:/]([^/]+/[^/]+)$|\1|; s|\.git$||')
  [[ -z "$r" ]] && return 0

  orgs=$(bash "$HELPER" config orgs --dir "$top" 2>/dev/null || echo '[]')
  printf '%s' "$orgs" | jq -e --arg o "${r%%/*}" 'length == 0 or index($o) != null' >/dev/null 2>&1 || return 0
  prefixes=$(bash "$HELPER" config branch_prefixes --dir "$top" 2>/dev/null || echo '[]')
  printf '%s' "$prefixes" | jq -e --arg b "$b" 'type == "array" and any(.[] | strings; . as $p | $b | startswith($p + "/"))' >/dev/null 2>&1 || return 0

  entry=$(bash "$HELPER" get --repo "$r" --branch "$b" --session "$session" 2>/dev/null)
  last=$(printf '%s' "$entry" | jq -r '.last_sha // ""' 2>/dev/null)
  [[ -n "$last" && "$head" == "$last"* ]] && return 0
  [[ -n "$toplevel" ]] && exit 0
  toplevel=$top branch=$b repo=$r existing=$entry
}

candidate "$cwd"
while IFS= read -r dir; do
  dir=$(gt_unquote "$dir")
  case "$dir" in '') continue ;; /*|[A-Za-z]:[/\\]*) ;; *) dir="$cwd/$dir" ;; esac
  candidate "$dir"
done < <(gt_strip_heredocs "$cmd" | grep -oE "(-C|cd)[[:space:]]+(\"[^\"]*\"|'[^']*'|[^[:space:];&|]+)" | sed -E 's/^(-C|cd)[[:space:]]+//')
[[ -z "$toplevel" ]] && exit 0

sha=$(git -C "$toplevel" rev-parse --short HEAD 2>/dev/null)
subject=$(git -C "$toplevel" log -1 --format=%s 2>/dev/null)

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

If SendMessage reports that agent as gone, it died with an earlier session: dispatch a fresh pr-guardian:pr-guardian agent for ${repo} @ ${branch} and re-register its handle with
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

  Agent({ subagent_type: "pr-guardian:pr-guardian", description: "guard ${branch}", prompt: "<the brief below>" })

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
