#!/usr/bin/env bash
# lock-guard.sh — PreToolUse/Bash. While a pr-guardian holds the write lock on a
# branch, block a `git commit` / `git push` on that branch from anyone else and name
# the guardian to message instead. Anything unexpected exits 0: never block on a broken guard.

set -uo pipefail

_scripts="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
HELPER="$_scripts/pr-guardian.sh"
[[ -r "$HELPER" && -r "$_scripts/git-target.sh" ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0
# shellcheck source=../scripts/git-target.sh
. "$_scripts/git-target.sh"

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
[[ -z "$cmd" || -z "$cwd" ]] && exit 0

gt_is_git_verb "$cmd" 'commit|push' || exit 0

repo_dir=$(gt_resolve_repo "$cmd" "$cwd")
[[ -z "$repo_dir" ]] && exit 0

branch=$(git -C "$repo_dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
[[ -z "$branch" || "$branch" == "HEAD" ]] && exit 0
remote=$(git -C "$repo_dir" remote get-url origin 2>/dev/null)
repo=$(printf '%s' "$remote" | sed -E 's|.*[:/]([^/]+/[^/]+)$|\1|; s|\.git$||')
[[ -z "$repo" ]] && exit 0

orgs=$(bash "$HELPER" config orgs --dir "$repo_dir" 2>/dev/null || echo '[]')
printf '%s' "$orgs" | jq -e --arg o "${repo%%/*}" 'length == 0 or index($o) != null' >/dev/null 2>&1 || exit 0

holder=$(bash "$HELPER" locked --repo "$repo" --branch "$branch" 2>/dev/null) || exit 0
[[ -z "$holder" ]] && exit 0

# Subagents share the parent's session_id, so the holder announces itself by prefixing
# its git command with PR_GUARDIAN=<holder>; anything else is a third party.
caller=$(printf '%s' "$cmd" | sed -nE 's/.*(^|[[:space:]])PR_GUARDIAN=([^[:space:]]+).*/\2/p' | head -1)
[[ -n "$caller" && "$caller" == "$holder" ]] && exit 0

agent=$(bash "$HELPER" get --repo "$repo" --branch "$branch" 2>/dev/null | jq -r '.agent // ""' 2>/dev/null)
[[ -z "$agent" ]] && agent="$holder"

IFS= read -r -d '' reason <<TXT || true
The PR guardian '${holder}' is mid-write on ${repo} @ ${branch} (rebase / amend / force-push in flight).

Committing or pushing now would race it — one of the two force-pushes wins and the other's work is gone.

Instead:
  SendMessage({ to: "${agent}", message: "<what you need — e.g. hold off, I have a new commit coming on ${branch}>" })

The lock is short-lived. Retry once the guardian releases it:
  bash "${HELPER}" locked --repo ${repo} --branch ${branch}   # exit 1 == free

If the guardian is gone and the lock is stale, it is released automatically after 30 minutes, or explicitly with:
  bash "${HELPER}" release --repo ${repo} --branch ${branch}

If you ARE '${holder}': you hold this lock, so write THROUGH it — prefix the command with your
holder string. Never release the lock to get past this guard; that reopens the race it exists to
prevent.
  PR_GUARDIAN=${holder} git commit --amend -F <file>
  PR_GUARDIAN=${holder} git push --force-with-lease
TXT

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
