#!/usr/bin/env bash
#
# run.sh: run one intake eval case headless, with or without the skill, and write one answer
# file <out-dir>/<case>.md for grade.py: the agent's reply per turn, then what the harness saw
# (commands run, files written, project changes after each turn, usage). Writes only to a
# temporary copy of the fixture and to <out-dir>, then deletes the session transcript claude
# leaves in ${CLAUDE_CONFIG_DIR:-~/.claude}/projects; a failed turn keeps it and prints where.

set -euo pipefail
export LC_ALL=C

usage() {
  cat <<USAGE
Usage: $(basename "${0}") <case> <with|without> <out-dir>

Runs the case's prompt and follow-up turns from evals.json with claude -p on a temporary copy
of its fixture, with the skill installed as a project skill (with) or not (without), and
writes <out-dir>/<case>.md. Needs claude and jq.
USAGE
}

[ $# -eq 3 ] || { usage >&2; exit 2; }
name=$1 arm=$2 out=$3
case "$arm" in
  with|without) ;;
  *) usage >&2; echo "arm must be with or without, got: $arm" >&2; exit 2 ;;
esac
for bin in claude jq; do
  command -v "$bin" >/dev/null 2>&1 || { echo "$bin is required but not found" >&2; exit 1; }
done

evals=$(cd "$(dirname "$0")" && pwd)
skill=$(dirname "$evals")
spec=$(jq -c --arg n "$name" '.evals[] | select(.name == $n)' "$evals/evals.json")
[ -n "$spec" ] || { echo "unknown case: $name" >&2; exit 2; }
answers="$evals/answers/$name.md"
[ -f "$answers" ] || { echo "missing answers file: $answers" >&2; exit 1; }

work=$(mktemp -d)
proj="$work/project"
cp -R "$evals/$(jq -r '.fixture' <<<"$spec")" "$proj"
if [ "$arm" = with ]; then
  mkdir -p "$proj/.claude/skills/intake"
  cp -R "$skill/SKILL.md" "$skill/reference.md" "$skill/references" "$skill/scripts" "$proj/.claude/skills/intake/"
fi

snap() {
  (
    cd "$proj"
    find . -path ./.claude -prune -o -path ./node_modules -prune -o -type f -exec cksum {} +
    if [ -d node_modules ]; then
      printf '%s 0 ./node_modules/\n' "$(find node_modules -type f | awk 'END { print NR }')"
    fi
  ) | sort -k3 > "$work/snap.$1"
}

changes() {
  awk '
    { p = $0; sub(/^[0-9]+ [0-9]+ /, "", p) }
    NR == FNR { seen[p] = $1 " " $2; next }
    !(p in seen) { print "- added " p; next }
    seen[p] != $1 " " $2 { print "- modified " p }
    { delete seen[p] }
    END { for (p in seen) print "- deleted " p }
  ' "$work/snap.0" "$work/snap.$1" | sort
}

events() { jq -R -c 'fromjson? // empty' "$work/turn$1.jsonl"; }

cc() {
  (cd "$proj" && MSYS_NO_PATHCONV=1 CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 \
    claude -p --model opus --setting-sources project --strict-mcp-config \
    --settings '{"disableAllHooks":true}' --permission-mode auto \
    --output-format stream-json --verbose "$@")
}

prompt=$(jq -r '.prompt' <<<"$spec")
[ "$arm" = with ] && prompt="/intake $prompt"
turns=$(( $(jq '.turns | length' <<<"$spec") + 1 ))
snap 0
session=""
for t in $(seq 1 "$turns"); do
  if [ "$t" -eq 1 ]; then
    cc -- "$prompt" > "$work/turn1.jsonl" 2> "$work/turn1.err" || true
    session=$(events 1 | jq -r 'select(.type == "system" and .subtype == "init") | .session_id' | head -n 1)
  elif [ -n "$session" ]; then
    msg=$(jq -r --rawfile a "$answers" --argjson i $((t - 2)) '.turns[$i] | gsub("\\{answers\\}"; $a)' <<<"$spec")
    cc --resume "$session" -- "$msg" > "$work/turn$t.jsonl" 2> "$work/turn$t.err" || true
  else
    : > "$work/turn$t.jsonl"
    echo "not run: turn 1 returned no session id" > "$work/turn$t.err"
  fi
  snap "$t"
done

failed=0
reply() {
  local r
  r=$(events "$1" | jq -s -r '[.[] | select(.type == "result")] | last | .result // empty')
  if [ -n "$r" ]; then
    printf '%s\n' "$r"
  else
    failed=1
    printf '(no reply: the turn failed: %s)\n' "$(tail -n 1 "$work/turn$1.err")"
  fi
}

tools() {
  events "$1" | jq -r --arg t "$1" --arg kind "$2" '
    select(.type == "assistant") | . as $e | .message.content[]? | select(.type == "tool_use")
    | "- turn \($t)\(if $e.parent_tool_use_id then " subagent" else "" end) \(.name): " as $head
    | if $kind == "commands run" and (.name == "Bash" or .name == "PowerShell") then
        $head + (.input.command | gsub("\n"; "\\n"))
      elif $kind == "files written" and .name == "Write" then
        $head + "\(.input.file_path) (\(.input.content | rtrimstr("\n") | split("\n") | length) lines)"
      elif $kind == "files written" and (.name == "Edit" or .name == "MultiEdit" or .name == "NotebookEdit") then
        $head + (.input.file_path // .input.notebook_path)
      else empty end'
}

section() {
  local t lines
  printf '## Harness: %s\n\n' "$1"
  lines=$(for t in $(seq 1 "$turns"); do tools "$t" "$1"; done)
  printf '%s\n\n' "${lines:-none}"
}

streams=()
for t in $(seq 1 "$turns"); do streams+=("$work/turn$t.jsonl"); done

mkdir -p "$out"
{
  for t in $(seq 1 "$turns"); do
    printf '## Turn %s\n\n' "$t"
    reply "$t"
    echo
  done
  section "commands run"
  section "files written"
  printf '## Harness: project changes\n\n'
  for t in $(seq 1 "$turns"); do
    printf '### After turn %s\n\n' "$t"
    c=$(changes "$t")
    printf '%s\n\n' "${c:-no change}"
  done
  printf '## Harness: usage\n\n'
  cat "${streams[@]}" | jq -R -s -r '[split("\n")[] | fromjson? // empty | select(.type == "result")] as $r
    | "\($r | length) turns, \(([$r[].duration_ms // 0] | add // 0) / 1000 | round) s, "
      + "\([$r[].usage | (.input_tokens // 0) + (.output_tokens // 0) + (.cache_creation_input_tokens // 0)
           + (.cache_read_input_tokens // 0)] | add // 0) tokens"'
} > "$out/$name.md"

projects="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
log=""
[ -n "$session" ] && [ -d "$projects" ] && log=$(find "$projects" -mindepth 2 -maxdepth 2 -name "$session.jsonl" -print -quit)
if [ "$failed" = 1 ]; then
  echo "a turn failed; streams kept in $work${log:+, session transcript in $log}" >&2
  exit 1
fi
rm -rf "$work"
# The suffix is the encoded temp cwd .../project: never delete a real project's transcripts.
case "${log%/*}" in *-project) rm -rf "${log%/*}" ;; esac
echo "$out/$name.md"
