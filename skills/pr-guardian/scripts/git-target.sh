#!/usr/bin/env bash
# git-target.sh — sourced by the pr-guardian hooks. Answers two questions:
#   1. is this Bash command really a git commit or push? Matches `git commit`,
#      `git -C <path> commit`, `env FOO=1 git commit`, `cd <path> && git commit` (same
#      for push); not `git diff|log|status|show`, nor a commit merely mentioned inside a
#      heredoc body or a quoted string.
#   2. which repository does it act on? The first `git -C <path>`, else a leading
#      `cd <path> &&|;`, else the session cwd — normalised with `rev-parse --show-toplevel`
#      so a linked worktree resolves to its own tree.
# No side effects, no `set` changes; bash + grep + sed only.

# Global `git` options that may sit between `git` and the subcommand; matched against
# sanitised text, where every quoted span is already the single token `Q`.
GT_GIT_OPT='(-C[[:space:]]*[^[:space:]]+|-c[[:space:]]+[^[:space:]]+|--no-pager|--paginate|--no-optional-locks|--literal-pathspecs|-P)'

# gt_collapse_quotes <line> — replace each quoted span by the single token `Q`, so
# `git -C "$WT" commit` stays parseable as `git -C Q commit`.
gt_collapse_quotes() {
  printf '%s' "$1" | sed -e "s/'[^']*'/Q/g" -e 's/"[^"]*"/Q/g'
}

# gt_strip_heredocs <cmd> — drop heredoc BODIES, keep every other line (the `<<EOF`
# line itself can carry a commit). `<<<` here-strings are left alone.
gt_strip_heredocs() {
  local line delim="" trimmed
  while IFS= read -r line || [ -n "$line" ]; do
    if [ -n "$delim" ]; then
      trimmed="${line#"${line%%[![:space:]]*}"}"
      trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
      trimmed="${trimmed%;}"
      if [ "$trimmed" = "$delim" ]; then delim=""; fi
      continue
    fi
    if [[ "$line" =~ \<\<-?[[:space:]]*[\"\']?([A-Za-z_][A-Za-z0-9_]*)[\"\']? ]]; then
      delim="${BASH_REMATCH[1]}"
    fi
    printf '%s\n' "$line"
  done <<< "$1"
}

# gt_sanitize_cmd <cmd> — heredoc bodies removed AND quoted spans collapsed: the text
# the command matchers run on.
gt_sanitize_cmd() {
  gt_strip_heredocs "$1" | sed -e "s/'[^']*'/Q/g" -e 's/"[^"]*"/Q/g'
}

# gt_is_git_verb <cmd> <verb-alternation>  e.g. gt_is_git_verb "$cmd" 'commit'
# Returns 0 when the command actually invokes `git <verb>`.
gt_is_git_verb() {
  local san
  san=$(gt_sanitize_cmd "$1")
  printf '%s\n' "$san" | grep -Eq \
    "(^|[^[:alnum:]_-])git([[:space:]]+${GT_GIT_OPT})*[[:space:]]+(${2})([^[:alnum:]_-]|\$)"
}

# gt_unquote <token> — strip one layer of quotes and expand a leading `~/`; prints
# nothing when the token still contains a shell expansion.
gt_unquote() {
  local p="$1"
  p="${p#"${p%%[![:space:]]*}"}"
  case "$p" in
    \"*\") p="${p#\"}"; p="${p%\"}" ;;
    \'*\') p="${p#\'}"; p="${p%\'}" ;;
  esac
  case "$p" in
    *'$'*|*'`'*|*'*'*) printf '' ; return 0 ;;
    '~') p="$HOME" ;;
    '~/'*) p="$HOME/${p#\~/}" ;;
  esac
  printf '%s' "$p"
}

# gt_command_path <cmd> — the path the command explicitly targets, or empty.
# Precedence: the first `git -C <path>`, then a leading `cd <path> &&|;`.
gt_command_path() {
  local stripped m p
  stripped=$(gt_strip_heredocs "$1")

  # First `git [-c k=v|--no-pager|…] -C <path>` on any line. grep -o reports
  # leftmost matches in order, so `head -1` is genuinely the FIRST occurrence.
  m=$(printf '%s\n' "$stripped" | grep -oE \
    "(^|[^[:alnum:]_-])git([[:space:]]+(-c[[:space:]]+[^[:space:]]+|--no-pager|--paginate|-P))*[[:space:]]+-C[[:space:]]*(\"[^\"]*\"|'[^']*'|[^[:space:]]+)" \
    | head -1) || m=""
  if [ -n "$m" ]; then
    p=$(gt_unquote "${m#*-C}")
    if [ -n "$p" ]; then printf '%s' "$p"; return 0; fi
  fi

  # Leading `cd <path> &&` / `cd <path> ;`
  m=$(printf '%s\n' "$stripped" | grep -oE \
    "^[[:space:]]*cd[[:space:]]+(\"[^\"]*\"|'[^']*'|[^[:space:];&|]+)" \
    | head -1) || m=""
  if [ -n "$m" ]; then
    p=$(gt_unquote "${m#*cd}")
    if [ -n "$p" ]; then printf '%s' "$p"; return 0; fi
  fi

  printf ''
}

# gt_resolve_repo <cmd> <cwd> — top-level of the repository the command acts on.
# Prints nothing when nothing resolves to a git repo (callers then pass).
gt_resolve_repo() {
  local cmd="$1" cwd="${2:-}" cand top
  [ -n "$cwd" ] || cwd="$PWD"
  cand=$(gt_command_path "$cmd")
  [ -n "$cand" ] || cand="$cwd"
  case "$cand" in
    /*) ;;
    *) cand="$cwd/$cand" ;;
  esac
  [ -d "$cand" ] || cand="$cwd"
  top=$(git -C "$cand" rev-parse --show-toplevel 2>/dev/null) || top=""
  printf '%s' "$top"
}
