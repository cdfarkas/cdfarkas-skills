#!/usr/bin/env bash
# pr-guardian.sh — registry, write lock, config, doctor and read-only plan for the
# pr-guardian agent. One entry per repo+branch; never hand-edit state.json.

set -uo pipefail

STATE_DIR="${PR_GUARDIAN_HOME:-$HOME/.pr-guardian}"
STATE_FILE="$STATE_DIR/state.json"
LOCK_DIR="$STATE_DIR/locks"
LOG="$STATE_DIR/pr-guardian.log"
DRY_RUN="${PR_GUARDIAN_DRY_RUN:-0}"
LOCK_STALE_SECONDS=1800
CONFIG_DEFAULTS='{"orgs":[],"pr":{"create":true,"sync_body":false},"commits":"stack","review_bots":[]}'

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" 2>/dev/null >> "$LOG" || true; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
dry() { (( DRY_RUN )) || return 1; echo "dry-run: would $*"; return 0; }

ensure() {
  mkdir -p "$STATE_DIR" "$LOCK_DIR" 2>/dev/null || true
  [[ -s "$STATE_FILE" ]] || echo '{"version":1,"guardians":[]}' > "$STATE_FILE"
  jq -e . "$STATE_FILE" >/dev/null 2>&1 || echo '{"version":1,"guardians":[]}' > "$STATE_FILE"
}

slug() { printf '%s' "$1/$2" | tr '/:@ ' '----' | tr -cd '[:alnum:]._-'; }

write_state() {
  local tmp
  tmp=$(mktemp) || return 1
  if jq "$@" "$STATE_FILE" > "$tmp" 2>/dev/null; then
    mv "$tmp" "$STATE_FILE"
  else
    rm -f "$tmp"
    return 1
  fi
}

usage() {
  cat <<'EOF'
Usage: pr-guardian.sh [--dry-run] <command> [options]

State of the pr-guardian agent: which guardian watches which branch, the write lock it
holds while it rewrites a branch, the per-repo configuration, and a read-only diagnosis.

Commands:
  register --repo <owner/name> --branch <ref> [--worktree <path>] [--agent <name>]
           [--session <id>] [--pr <number>] [--sha <sha>]
        Create or refresh the entry for repo+branch; prints its id. Call it again with
        --agent (or `set --agent`) right after the Agent tool returns the handle.
  get      --repo <owner/name> --branch <ref> [--session <id>]
        Print the entry as JSON (nothing if none). With --session, an entry owned by
        another session is reported with status "lost".
  list     [--json|--text] [--session <id>]
  set      --id <id> [--agent <n>] [--pr <n>] [--sha <s>] [--status <s>] [--note <text>] [--orphan]
        --orphan marks the entry adoptable: its guardian's session ended.
  acquire  --repo <r> --branch <b> --holder <who>     take the write lock; exit 1 if held
  release  --repo <r> --branch <b>
  locked   --repo <r> --branch <b>                    exit 0 and print the holder if held
  done     --repo <r> --branch <b>                    PR merged or guardian finished
  prune    [--max-age-days N]                         drop entries and locks older than N days (7)
  config   <key> [--dir <repo>]                       print one setting as JSON
        Keys and defaults: orgs [] · pr.create true · commits "stack" · pr.sync_body false
        · review_bots []. Read from .pr-guardian.json at the repo root, else
        ~/.config/pr-guardian.json, else the default.
  plan     --repo <owner/name> --branch <ref> [--dir <repo>]
        Read-only diagnosis: the PR, distance to the default branch, checks, review,
        then one `next:` line per action a guardian would take. Never writes.
  doctor | --doctor
        Check bash, git, gh (auth, repo scope), jq, timeout, the shell and the state
        dir — one ok/FAIL/skip line each, exit 1 on the first FAIL.
  -h, --help

--dry-run   Every mutating command (register, set, done, acquire, release, prune) prints
            `dry-run: would <action>` and writes nothing. Also PR_GUARDIAN_DRY_RUN=1.

State lives in $PR_GUARDIAN_HOME (default ~/.pr-guardian): state.json, locks/, pr-guardian.log.
Requires bash 3.2+, git, gh, jq and coreutils timeout — on Windows, Git Bash.
EOF
}

cmd_register() {
  local repo="" branch="" worktree="" agent="" session="" pr="" sha=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)     repo="$2";     shift 2;;
      --branch)   branch="$2";   shift 2;;
      --worktree) worktree="$2"; shift 2;;
      --agent)    agent="$2";    shift 2;;
      --session)  session="$2";  shift 2;;
      --pr)       pr="$2";       shift 2;;
      --sha)      sha="$2";      shift 2;;
      *) shift;;
    esac
  done
  [[ -z "$repo" || -z "$branch" ]] && { echo "register: need --repo and --branch" >&2; return 1; }
  dry "register $repo@$branch${agent:+ agent=$agent}${sha:+ sha=$sha}" && return 0
  ensure

  local existing
  existing=$(jq -r --arg r "$repo" --arg b "$branch" \
    'first(.guardians[] | select(.status!="done" and .repo==$r and .branch==$b) | .id) // ""' \
    "$STATE_FILE")

  if [[ -n "$existing" ]]; then
    write_state --arg id "$existing" --arg agent "$agent" --arg session "$session" \
      --arg pr "$pr" --arg sha "$sha" --arg now "$(now)" '
      .guardians |= map(
        if .id == $id then
          (if $agent   != "" then .agent      = $agent   else . end)
          | (if $session != "" then .session_id = $session else . end)
          | (if $pr      != "" then .pr         = $pr      else . end)
          | (if $sha     != "" then .last_sha   = $sha     else . end)
          | .status = "live"
          | .updated_at = $now
          | .orphaned_at = null
          | .pushes = ((.pushes // 0) + 1)
        else . end)'
    log "register: refresh $existing $repo@$branch agent=${agent:-?}"
    echo "$existing"
    return 0
  fi

  local id="grd_$(date +%s)_${RANDOM}"
  write_state --arg id "$id" --arg repo "$repo" --arg branch "$branch" \
    --arg worktree "$worktree" --arg agent "$agent" --arg session "$session" \
    --arg pr "$pr" --arg sha "$sha" --arg now "$(now)" '
    .guardians += [{
      id: $id, repo: $repo, branch: $branch, worktree: $worktree,
      agent: $agent, session_id: $session, pr: $pr, last_sha: $sha,
      status: "live", pushes: 1, notes: [],
      created_at: $now, updated_at: $now
    }]'
  log "register: new $id $repo@$branch agent=${agent:-?}"
  echo "$id"
}

cmd_get() {
  local repo="" branch="" session=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)    repo="$2";    shift 2;;
      --branch)  branch="$2";  shift 2;;
      --session) session="$2"; shift 2;;
      *) shift;;
    esac
  done
  ensure
  jq -c --arg r "$repo" --arg b "$branch" --arg s "$session" '
    first(.guardians[] | select(.status!="done" and .repo==$r and .branch==$b))
    | if . == null then empty
      elif (.status == "live" and $s != "" and .session_id != "" and .session_id != $s)
      then . + {status: "lost"}
      else . end' "$STATE_FILE"
}

cmd_list() {
  local fmt="--text" session=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json|--text) fmt="$1"; shift;;
      --session) session="$2"; shift 2;;
      *) shift;;
    esac
  done
  ensure
  if [[ "$fmt" == "--json" ]]; then
    jq --arg s "$session" '[.guardians[]
      | select(.status!="done")
      | select($s == "" or .session_id == "" or .session_id == $s)]' "$STATE_FILE"
    return
  fi
  jq -r --arg s "$session" '.guardians[]
    | select(.status!="done")
    | select($s == "" or .session_id == "" or .session_id == $s)
    | "- [\(.id)] \(.repo) @ \(.branch)\(if .pr != "" then " (PR #"+.pr+")" else "" end) — \(.status), agent: \(if .agent != "" then .agent else "UNREGISTERED" end) (updated \(.updated_at))"' \
    "$STATE_FILE"
}

cmd_set() {
  local id="" agent="" pr="" sha="" status="" note="" orphan=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --orphan) orphan=1;    shift;;
      --id)     id="$2";     shift 2;;
      --agent)  agent="$2";  shift 2;;
      --pr)     pr="$2";     shift 2;;
      --sha)    sha="$2";    shift 2;;
      --status) status="$2"; shift 2;;
      --note)   note="$2";   shift 2;;
      *) shift;;
    esac
  done
  [[ -z "$id" ]] && { echo "set: need --id" >&2; return 1; }
  dry "set $id${agent:+ agent=$agent}${pr:+ pr=$pr}${sha:+ sha=$sha}${status:+ status=$status}${note:+ note=\"$note\"}$( (( orphan )) && echo ' orphan')" && return 0
  ensure
  write_state --arg id "$id" --arg agent "$agent" --arg pr "$pr" --arg sha "$sha" \
    --arg status "$status" --arg note "$note" --arg now "$(now)" --argjson orphan "$orphan" '
    .guardians |= map(
      if .id == $id then
        (if $agent  != "" then .agent    = $agent  else . end)
        | (if $pr     != "" then .pr       = $pr     else . end)
        | (if $sha    != "" then .last_sha = $sha    else . end)
        | (if $status != "" then .status   = $status else . end)
        | (if $note   != "" then .notes    = ((.notes // []) + [{at: $now, text: $note}]) else . end)
        | (if $orphan == 1 then .status = "orphaned" | .orphaned_at = $now else . end)
        | .updated_at = $now
      else . end)'
  log "set: $id agent=${agent:-} pr=${pr:-} status=${status:-}$( (( orphan )) && echo ' orphan')"
}

cmd_acquire() {
  local repo="" branch="" holder="guardian"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)   repo="$2";   shift 2;;
      --branch) branch="$2"; shift 2;;
      --holder) holder="$2"; shift 2;;
      *) shift;;
    esac
  done
  [[ -z "$repo" || -z "$branch" ]] && { echo "acquire: need --repo and --branch" >&2; return 1; }
  dry "acquire the write lock on $repo@$branch for $holder" && return 0
  ensure
  local dir="$LOCK_DIR/$(slug "$repo" "$branch").lock"
  if mkdir "$dir" 2>/dev/null; then
    printf '%s\n%s\n' "$holder" "$(now)" > "$dir/holder"
    log "acquire: $repo@$branch by $holder"
    return 0
  fi
  echo "held by: $(head -1 "$dir/holder" 2>/dev/null || echo unknown)" >&2
  return 1
}

cmd_release() {
  local repo="" branch=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)   repo="$2";   shift 2;;
      --branch) branch="$2"; shift 2;;
      *) shift;;
    esac
  done
  dry "release the write lock on $repo@$branch" && return 0
  ensure
  local dir="$LOCK_DIR/$(slug "$repo" "$branch").lock"
  rm -f "$dir/holder" 2>/dev/null || true
  rmdir "$dir" 2>/dev/null || true
  log "release: $repo@$branch"
}

cmd_locked() {
  local repo="" branch=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)   repo="$2";   shift 2;;
      --branch) branch="$2"; shift 2;;
      *) shift;;
    esac
  done
  local dir="$LOCK_DIR/$(slug "$repo" "$branch").lock"
  [[ -d "$dir" ]] || return 1
  local mtime age
  mtime=$(stat -f %m "$dir" 2>/dev/null || stat -c %Y "$dir" 2>/dev/null || echo 0)
  age=$(( $(date +%s) - mtime ))
  if (( age > LOCK_STALE_SECONDS )); then
    log "locked: stale lock ($age s) on $repo@$branch — releasing"
    rm -f "$dir/holder" 2>/dev/null || true
    rmdir "$dir" 2>/dev/null || true
    return 1
  fi
  head -1 "$dir/holder" 2>/dev/null || echo unknown
  return 0
}

cmd_done() {
  local repo="" branch=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)   repo="$2";   shift 2;;
      --branch) branch="$2"; shift 2;;
      *) shift;;
    esac
  done
  dry "mark $repo@$branch done and release its lock" && return 0
  ensure
  write_state --arg r "$repo" --arg b "$branch" --arg now "$(now)" '
    .guardians |= map(
      if .status!="done" and .repo==$r and .branch==$b
      then .status="done" | .updated_at=$now else . end)'
  cmd_release --repo "$repo" --branch "$branch"
  log "done: $repo@$branch"
}

cmd_prune() {
  local days=7
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max-age-days) days="$2"; shift 2;;
      *) shift;;
    esac
  done
  dry "prune entries and locks older than $days day(s)" && return 0
  ensure
  local cutoff
  cutoff=$(( $(date +%s) - days * 86400 ))
  write_state --argjson cutoff "$cutoff" '
    .guardians |= map(select(
      .status != "done" and ((.id | split("_")[1] | tonumber?) // 0) >= $cutoff
    ))'
  local d mtime
  for d in "$LOCK_DIR"/*.lock; do
    [[ -d "$d" ]] || continue
    mtime=$(stat -f %m "$d" 2>/dev/null || stat -c %Y "$d" 2>/dev/null || echo 0)
    (( mtime < cutoff )) && { rm -rf "$d"; log "prune: stale lock $d"; }
  done
  log "prune: max-age ${days}d"
}

cmd_config() {
  local key="" dir="."
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dir) dir="$2"; shift 2;;
      *) [[ -z "$key" ]] && key="$1"; shift;;
    esac
  done
  [[ -z "$key" ]] && { echo "config: need a key (orgs, pr.create, commits, pr.sync_body, review_bots)" >&2; return 1; }
  local top file=""
  top=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null) || top=""
  [[ -n "$top" && -f "$top/.pr-guardian.json" ]] && file="$top/.pr-guardian.json"
  [[ -z "$file" && -f "$HOME/.config/pr-guardian.json" ]] && file="$HOME/.config/pr-guardian.json"
  if [[ -n "$file" ]] && jq -e . "$file" >/dev/null 2>&1; then
    jq -c --arg k "$key" --argjson d "$CONFIG_DEFAULTS" '($d * .) | getpath($k | split("."))' "$file"
  else
    [[ -n "$file" ]] && echo "config: $file is not valid JSON, using defaults" >&2
    jq -cn --arg k "$key" --argjson d "$CONFIG_DEFAULTS" '$d | getpath($k | split("."))'
  fi
}

cmd_plan() {
  local repo="" branch="" dir=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)   repo="$2";   shift 2;;
      --branch) branch="$2"; shift 2;;
      --dir)    dir="$2";    shift 2;;
      *) shift;;
    esac
  done
  [[ -z "$repo" || -z "$branch" ]] && { echo "plan: need --repo and --branch" >&2; return 1; }
  local base pr next=""
  base=$(gh repo view "$repo" --json defaultBranchRef --jq .defaultBranchRef.name 2>/dev/null) || base=""
  [[ -z "$base" ]] && { echo "plan: cannot read $repo (gh repo view failed — auth, name or network)" >&2; return 1; }
  pr=$(gh pr view "$branch" --repo "$repo" \
        --json number,url,isDraft,mergeable,mergeStateStatus,state,statusCheckRollup,body 2>/dev/null) || pr=""

  if [[ -z "$pr" ]]; then
    echo "pr: none open for $branch on $repo (base $base)"
    if [[ "$(cmd_config pr.create --dir "${dir:-.}")" == "true" ]]; then
      next="next: open a PR from $branch onto $base"
    else
      next="next: nothing until a PR exists (pr.create is false)"
    fi
    printf '%s\n' "$next"
    return 0
  fi

  local number url draft mergeable mss state behind failing pending
  number=$(jq -r .number <<< "$pr"); url=$(jq -r .url <<< "$pr")
  draft=$(jq -r .isDraft <<< "$pr"); mergeable=$(jq -r '.mergeable // "UNKNOWN"' <<< "$pr")
  mss=$(jq -r '.mergeStateStatus // "UNKNOWN"' <<< "$pr"); state=$(jq -r .state <<< "$pr")
  echo "pr: #$number $url draft=$draft mergeable=$mergeable state=$mss"
  if [[ "$state" == "MERGED" || "$state" == "CLOSED" ]]; then
    echo "next: nothing — PR is $state"
    return 0
  fi

  behind=$(gh api "repos/$repo/compare/$base...$branch" --jq .behind_by 2>/dev/null) || behind="?"
  echo "base: $base, behind by $behind commit(s)"
  if [[ "$mergeable" == "CONFLICTING" || ( "$behind" != "0" && "$behind" != "?" ) ]]; then
    next="${next}next: rebase $branch on $base"$'\n'
  fi

  failing=$(jq -r '[(.statusCheckRollup // [])[]
    | select(((.conclusion // .state // "") | ascii_upcase) | test("FAILURE|TIMED_OUT|CANCELLED|ACTION_REQUIRED|ERROR"))
    | .name // .context] | join(", ")' <<< "$pr")
  pending=$(jq -r '[(.statusCheckRollup // [])[]
    | select(((.status // .state // "") | ascii_upcase) | test("IN_PROGRESS|QUEUED|PENDING|EXPECTED"))] | length' <<< "$pr")
  echo "checks: ${failing:-none failing}, $pending pending"
  local name
  while IFS= read -r name; do
    [[ -n "$name" ]] && next="${next}next: fix check $name"$'\n'
  done <<< "${failing//, /$'\n'}"
  [[ "$pending" != "0" ]] && next="${next}next: wait for $pending pending check(s)"$'\n'

  local rv latest unresolved
  rv=$(gh api graphql -F o="${repo%%/*}" -F r="${repo#*/}" -F n="$number" -f query='
    query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ pullRequest(number:$n){
      reviews(last:1){nodes{author{login} state submittedAt}}
      reviewThreads(last:100){nodes{isResolved}} } } }' 2>/dev/null) || rv='{}'
  latest=$(jq -r '.data.repository.pullRequest.reviews.nodes[0]?
    | if . == null then "none" else "\(.author.login) \(.state) at \(.submittedAt)" end' <<< "$rv")
  unresolved=$(jq -r '[.data.repository.pullRequest.reviewThreads.nodes[]? | select(.isResolved | not)] | length' <<< "$rv")
  echo "review: $latest, $unresolved unresolved thread(s)"
  if [[ "$latest" == *CHANGES_REQUESTED* || "$unresolved" != "0" ]]; then
    next="${next}next: answer the review ($unresolved unresolved thread(s))"$'\n'
  fi

  if [[ -n "$dir" && "$(cmd_config pr.sync_body --dir "$dir")" == "true" ]]; then
    local body; body=$(git -C "$dir" log -1 --format=%b 2>/dev/null || echo)
    [[ "$(printf '%s' "$body" | tr -d '\r')" != "$(jq -r '.body // ""' <<< "$pr" | tr -d '\r')" ]] \
      && next="${next}next: resync the PR body from the head commit"$'\n'
  fi

  [[ -z "$next" ]] && next="next: nothing — mergeable, checks green, no review pending"$'\n'
  printf '%s' "$next"
}

_install_hint() {
  case "$(uname -s)" in
    Darwin) echo "brew install $1" ;;
    MINGW*|MSYS*|CYGWIN*|Windows*) echo "winget install $2" ;;
    *) echo "apt install $1 / dnf install $1" ;;
  esac
}

cmd_doctor() {
  if (( BASH_VERSINFO[0] > 3 || (BASH_VERSINFO[0] == 3 && BASH_VERSINFO[1] >= 2) )); then echo "ok    bash: $BASH_VERSION"
  else echo "FAIL  bash: $BASH_VERSION, need 3.2 or newer ($(_install_hint bash Git.Git))"; return 1; fi

  if command -v git >/dev/null 2>&1; then echo "ok    git: $(command -v git)"
  else echo "FAIL  git: not installed ($(_install_hint git Git.Git))"; return 1; fi

  if command -v gh >/dev/null 2>&1; then echo "ok    gh: $(command -v gh)"
  else echo "FAIL  gh: not installed ($(_install_hint gh GitHub.cli))"; return 1; fi
  if gh auth status >/dev/null 2>&1; then
    echo "ok    gh auth: $(gh api user --jq .login 2>/dev/null || echo authenticated)"
  else echo "FAIL  gh auth: not authenticated (gh auth login)"; return 1; fi
  local scopes
  scopes=$(gh api -i user 2>/dev/null | tr -d '\r' | sed -n 's/^[Xx]-[Oo][Aa]uth-[Ss]copes: *//p' | head -1)
  if [[ -z "$scopes" ]]; then echo "skip  scopes: fine-grained token, cannot verify"
  elif [[ " $(printf '%s' "$scopes" | tr ',' ' ') " == *" repo "* ]]; then echo "ok    scopes: $scopes"
  else echo "FAIL  scopes: token lacks the repo scope (gh auth refresh -s repo); have: $scopes"; return 1; fi

  if command -v jq >/dev/null 2>&1; then echo "ok    jq: $(command -v jq)"
  else echo "FAIL  jq: not installed ($(_install_hint jq jqlang.jq))"; return 1; fi

  if command -v timeout >/dev/null 2>&1; then echo "ok    timeout: $(command -v timeout)"
  elif command -v gtimeout >/dev/null 2>&1; then echo "ok    timeout: $(command -v gtimeout)"
  else
    case "$(uname -s)" in
      Darwin) echo "FAIL  timeout: not installed (brew install coreutils)" ;;
      MINGW*|MSYS*|CYGWIN*|Windows*) echo "FAIL  timeout: not found; it ships with Git for Windows (winget install Git.Git)" ;;
      *) echo "FAIL  timeout: not installed (apt install coreutils / dnf install coreutils)" ;;
    esac
    return 1
  fi

  local os; os=$(uname -s 2>/dev/null || echo unknown)
  case "$os" in
    MINGW*|MSYS*|CYGWIN*) echo "ok    shell: Git Bash ($os)" ;;
    *)
      if [[ "${OS:-}" == "Windows_NT" && -z "${MSYSTEM:-}" ]]; then
        echo "FAIL  shell: run under Git Bash (Git for Windows)"; return 1
      fi
      echo "ok    shell: bash on $os" ;;
  esac

  if mkdir -p "$STATE_DIR" 2>/dev/null && [[ -w "$STATE_DIR" ]]; then echo "ok    state: $STATE_DIR"
  else echo "FAIL  state: cannot create or write $STATE_DIR (set PR_GUARDIAN_HOME to a writable dir)"; return 1; fi
}

_args=()
for _a in "$@"; do
  if [[ "$_a" == "--dry-run" ]]; then DRY_RUN=1; else _args+=("$_a"); fi
done
set -- ${_args[@]+"${_args[@]}"}

case "${1:-}" in
  register) shift; cmd_register "$@";;
  get)      shift; cmd_get "$@";;
  list)     shift; cmd_list "$@";;
  set)      shift; cmd_set "$@";;
  acquire)  shift; cmd_acquire "$@";;
  release)  shift; cmd_release "$@";;
  locked)   shift; cmd_locked "$@";;
  done)     shift; cmd_done "$@";;
  prune)    shift; cmd_prune "$@";;
  config)   shift; cmd_config "$@";;
  plan)     shift; cmd_plan "$@";;
  doctor|--doctor) cmd_doctor;;
  -h|--help) usage; exit 0;;
  "") usage; exit 1;;
  *) echo "unknown command: $1" >&2; usage >&2; exit 2;;
esac
