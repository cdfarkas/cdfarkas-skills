#!/usr/bin/env bash
#
# front-review: resolve one review target and print a deterministic review context for a
# front-end code review: the changed front files grouped by rule axis, the repo's REVIEW.md
# overlay read from the base ref, contract files, gates detected from config files, the floor
# in effect, candidate findings with file:line that the review must carry, and the severity
# vocabulary of the report language.
#
# Read-only: it never writes to the working tree, never checks out, never calls a GitHub
# write endpoint. A pull request target fetches the PR head into the object store only.

set -euo pipefail
export LC_ALL=C

TAB="$(printf '\t')"
_TARGET=""
_LANG_FLAG=""

usage() {
  cat <<USAGE
Usage: $(basename "${0}") [<target>] [--lang en|fr]

Prints the review context of a front-end change.

  <target>     a path (every front file under it, reviewed as new), a branch, a revision
               range (A..B, A...B), a pull request number or URL (needs gh), or nothing
               for the working diff against the merge base with the default branch
  --lang       report language when the overlay sets none (default: en)
  -h, --help   this help
USAGE
}

die() { echo "$1" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --lang) [ $# -ge 2 ] || { usage >&2; echo "--lang needs a value (en|fr)" >&2; exit 2; }
            _LANG_FLAG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --*) usage >&2; echo "unknown flag: $1" >&2; exit 2 ;;
    (*) [ -z "$_TARGET" ] || { usage >&2; echo "one target only, got: $_TARGET and $1" >&2; exit 2; }
       _TARGET="$1"; shift ;;
  esac
done
case "$_LANG_FLAG" in ""|en|fr) ;; (*) echo "unknown language: $_LANG_FLAG (en|fr)" >&2; exit 2 ;; esac

_TMP="$(mktemp -d)"
trap 'rm -rf "$_TMP"' EXIT

_KIND=""; _PR=""; _B=""; _H=""; _UP=""; _MB=""
case "$_TARGET" in
  "") _KIND=working ;;
  (*[!0-9]*)
    if printf '%s' "$_TARGET" | grep -Eq '/pull/[0-9]+/?$'; then
      _KIND=pr; _PR="${_TARGET%/}"; _PR="${_PR##*/}"
    elif [ -e "$_TARGET" ]; then _KIND=path
    else case "$_TARGET" in (*..*) _KIND=range ;; (*) _KIND=branch ;; esac
    fi ;;
  (*) _KIND=pr; _PR="$_TARGET" ;;
esac

_git_top() {
  local top
  top="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not a git repository: $(pwd)"
  cd "$top"
}

_default_branch() {
  local r
  r="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD || true)"
  [ -n "$r" ] && { echo "$r"; return 0; }
  for r in origin/main origin/master main master; do
    git rev-parse --verify --quiet "$r^{commit}" >/dev/null && { echo "$r"; return 0; }
  done
  die "no default branch found (tried origin/HEAD, origin/main, origin/master, main, master)"
}

_verify() { git rev-parse --verify --quiet "$1^{commit}" >/dev/null || die "unknown revision: $1"; }

case "$_KIND" in
  path)
    if [ -d "$_TARGET" ]; then cd "$_TARGET"; _ONLY=""
    else cd "$(dirname "$_TARGET")"; _ONLY="$(basename "$_TARGET")"; fi
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      _UP="$(git rev-parse --show-cdup)"; _UP="${_UP%/}"
      if [ -n "$_ONLY" ]; then echo "$_ONLY"; else git ls-files -co --exclude-standard; fi
    elif [ -n "$_ONLY" ]; then echo "$_ONLY"
    else find . -type f -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/dist/*' | sed 's|^\./||'
    fi > "$_TMP/changed" ;;
  working)
    _git_top; _B="$(_default_branch)"
    _MB="$(git merge-base "$_B" HEAD)" || die "no merge base between $_B and HEAD"
    { git diff --name-only --diff-filter=d "$_MB"; git ls-files -o --exclude-standard; } | sort -u > "$_TMP/changed" ;;
  branch)
    _git_top; _verify "$_TARGET"; _B="$(_default_branch)"; _H="$_TARGET"
    _MB="$(git merge-base "$_B" "$_H")" || die "no merge base between $_B and $_H"
    git diff --name-only --diff-filter=d "$_MB" "$_H" > "$_TMP/changed" ;;
  range)
    _git_top; _B="${_TARGET%%..*}"; _H="${_TARGET##*..}"
    [ -n "$_B" ] || die "unknown target: $_TARGET (a range needs a start revision)"
    [ -n "$_H" ] || _H=HEAD
    _verify "$_B"; _verify "$_H"
    git diff --name-only --diff-filter=d "$_TARGET" > "$_TMP/changed" ;;
  pr)
    command -v gh >/dev/null 2>&1 || die "gh is required for a pull request target but not found"
    _git_top
    _META="$(gh pr view "$_PR" --json baseRefName,headRefOid --jq '.baseRefName + " " + .headRefOid' 2>"$_TMP/err")" \
      || { tail -n 1 "$_TMP/err" >&2; die "gh pr view $_PR failed"; }
    _H="${_META##* }"; _B="origin/${_META%% *}"
    git fetch --quiet origin "${_META%% *}" "pull/$_PR/head" || die "cannot fetch pull request $_PR from origin"
    git cat-file -e "$_H^{commit}" || die "head $_H of pull request $_PR is missing after the fetch"
    _MB="$(git merge-base "$_B" "$_H")" || die "no merge base between $_B and $_H"
    git diff --name-only --diff-filter=d "$_MB" "$_H" > "$_TMP/changed" ;;
esac

# Accessors: ref "" is the working tree, any other value a git revision.
_cat() { if [ -z "$1" ]; then tr -d '\r' < "$2"; else git show "$1:$2" | tr -d '\r'; fi; }
_has() { if [ -z "$1" ]; then [ -f "$2" ]; else git cat-file -e "$1:$2" 2>/dev/null; fi; }
_isdir() { if [ -z "$1" ]; then [ -d "$2" ]; else [ "$(git cat-file -t "$1:$2" 2>/dev/null)" = tree ]; fi; }
_ls() {
  if [ -z "$1" ]; then if [ -d "$2" ]; then ls -1A "$2"; fi
  elif [ "$2" = . ]; then git ls-tree --name-only "$1:"
  else git ls-tree --name-only "$1:$2" 2>/dev/null || true; fi
}
_join() { if [ "$1" = . ]; then echo "$2"; else echo "$1/$2"; fi; }
_dir() { local d="${1%/*}"; [ "$d" = "$1" ] && d=.; echo "$d"; }
# Subshell-free variants for hot loops (forks are slow under Git Bash): set _J / _D.
_joinv() { if [ "$1" = . ]; then _J="$2"; else _J="$1/$2"; fi; }
_dirv() { _D="${1%/*}"; [ "$_D" != "$1" ] || _D=.; }
_short() { if [ -z "$1" ]; then echo "working tree"; else echo "$1 $(git rev-parse --short "$1^{commit}")"; fi; }

_group() {
  case "$1" in
    node_modules/*|*/node_modules/*) _G=skip ;;
    (*.stories.*|*.story.*|*.test.*|*.spec.*|*/__tests__/*)
      case "$1" in (*.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.mdx) _G=test ;; (*) _G=skip ;; esac ;;
    (*.css|*.scss|*.sass|*.less) _G=css ;;
    (*.tsx|*.jsx) _G=tsx ;;
    (*.ts|*.js|*.mjs|*.cjs|*.mts|*.cts)
      case "${1##*/}" in
        vite.config.*|rollup.config.*|rolldown.config.*|tsup.config.*|tsdown.config.*|webpack.config.*|esbuild.config.*) _G=build ;;
        (*.d.ts|*.config.*|.*) _G=skip ;;
        (*) _G=ts ;;
      esac ;;
    package.json|*/package.json|.size-limit*|*/.size-limit*) _G=build ;;
    (*) _G=skip ;;
  esac
}

: > "$_TMP/front"
while IFS= read -r f; do
  [ -n "$f" ] || continue
  _group "$f"; g="$_G"
  [ "$g" = skip ] || printf '%s\t%s\n' "$g" "$f" >> "$_TMP/front"
done < "$_TMP/changed"
sort -o "$_TMP/front" "$_TMP/front"
_files() { awk -F "$TAB" -v g="$1" '$1 == g { print $2 }' "$_TMP/front"; }

# Every directory that covers a front file, root first; above-root ones (path targets) before it.
{
  echo .
  cut -f2 "$_TMP/front" | while IFS= read -r f; do
    _dirv "$f"
    while [ "$_D" != . ]; do echo "$_D"; _dirv "$_D"; done
  done
  up=""
  while [ -n "$_UP" ] && [ "$up" != "$_UP" ]; do up="${up:+$up/}.."; echo "$up"; done
} | sort -u | awk '{ k = ($0 == ".") ? 0 : ($0 ~ /^\.\./) ? -gsub(/\.\./, "&") : gsub(/\//, "&") + 1; print k "\t" $0 }' \
  | sort -t "$TAB" -k1,1n -k2,2 | cut -f2 > "$_TMP/dirs"
_top_dirs() { grep -E '^(\.|\.\.(/\.\.)*)$' "$_TMP/dirs"; }

_nearest_pkg() {
  local up=""
  _dirv "$1"
  while :; do
    _joinv "$_D" package.json
    _has "$_H" "$_J" && { echo "$_J"; return 0; }
    [ "$_D" = . ] && break
    _dirv "$_D"
  done
  while [ -n "$_UP" ] && [ "$up" != "$_UP" ]; do
    up="${up:+$up/}.."
    _has "" "$up/package.json" && { echo "$up/package.json"; return 0; }
  done
  return 0
}

_publishable() {
  local body
  body="$(_cat "$_H" "$1")"
  if printf '%s' "$body" | grep -Eq '"private"[[:space:]]*:[[:space:]]*true'; then echo "no: private"
  elif printf '%s' "$body" | grep -Eq '"(exports|main)"[[:space:]]*:'; then echo "yes"
  else echo "no: no exports or main"; fi
}

_section() {
  awk -v h="$2" '
    /^## / { s = tolower(substr($0, 4)); sub(/[ \t]+$/, "", s); on = (s ~ h); next }
    /^# / { on = 0 }
    on { print }' "$1" \
  | awk 'NF { started = 1 } started { a[++n] = $0 } END { while (n > 0 && a[n] !~ /[^ \t]/) n--; for (i = 1; i <= n; i++) print a[i] }'
}

: > "$_TMP/ov.list"
_i=0
while IFS= read -r d; do
  p="$(_join "$d" REVIEW.md)"
  _has "$_B" "$p" || continue
  _i=$((_i + 1))
  _cat "$_B" "$p" > "$_TMP/ov.$_i"
  _section "$_TMP/ov.$_i" '^do not report$' | sed 's/\*\*//g' | tr -c 'A-Za-z0-9*_-' '\n' \
    | grep -xE '[ARUPT]([0-9]{1,2}|\*)' | sort -u > "$_TMP/ov.$_i.off" || true
  printf '%s\t%s\t%s\n' "$d" "$p" "$_i" >> "$_TMP/ov.list"
done < "$_TMP/dirs"

_LANG=""; _LANG_SRC=""
while IFS="$TAB" read -r d p i; do
  l="$(_section "$_TMP/ov.$i" '^language$' | head -n 1 | tr 'A-Z' 'a-z' | sed 's/^[-* ]*//')"
  case "$l" in
    fr*) _LANG=fr; _LANG_SRC="$p ## Language"; break ;;
    en*) _LANG=en; _LANG_SRC="$p ## Language"; break ;;
  esac
done < "$_TMP/ov.list"
if [ -z "$_LANG" ]; then
  if [ -n "$_LANG_FLAG" ]; then _LANG="$_LANG_FLAG"; _LANG_SRC="--lang"; else _LANG=en; _LANG_SRC="default"; fi
fi

_off_by() {
  local letter="${2%%[0-9]*}" d p i
  while IFS="$TAB" read -r d p i; do
    case "$d" in .|..*) ;; (*) case "$1" in "$d"/*) ;; (*) continue ;; esac ;; esac
    if grep -qxF -e "$2" -e "$letter*" "$_TMP/ov.$i.off"; then echo "$p"; return 0; fi
  done < "$_TMP/ov.list"
  return 0
}

: > "$_TMP/gatefiles"
while IFS= read -r d; do
  for n in $(_ls "$_H" "$d"); do
    _joinv "$d" "$n"; p="$_J"
    case "$n" in
      eslint.config.*|.eslintrc|.eslintrc.*) echo "eslint$TAB$p" ;;
      stylelint.config.*|.stylelintrc|.stylelintrc.*) echo "stylelint$TAB$p" ;;
      tsconfig.json) echo "tsc$TAB$p" ;;
      .size-limit|.size-limit.*) echo "size-limit$TAB$p" ;;
      package.json) echo "pkg$TAB$p" ;;
    esac
  done
  for n in $(_ls "$_H" "$(_join "$d" .github/workflows)"); do
    case "$n" in (*.yml|*.yaml) echo "ci$TAB$(_join "$d" .github/workflows/"$n")" ;; esac
  done
done < "$_TMP/dirs" >> "$_TMP/gatefiles"
_gate() { awk -F "$TAB" -v k="$1" '$1 == k { print $2 }' "$_TMP/gatefiles"; }

: > "$_TMP/pkgs.txt"
for p in $(_gate pkg); do _cat "$_H" "$p" >> "$_TMP/pkgs.txt"; done
_deps() { { grep -oE "\"($1)\"[[:space:]]*:" "$_TMP/pkgs.txt" || true; } | sed -E 's/"([^"]*)".*/\1/' | sort -u | tr '\n' ' ' | sed 's/ $//'; }

_ESLINT="$(_gate eslint | tr '\n' ' ' | sed 's/ $//')"
_ESL_TEXT=""
for p in $(_gate eslint); do _ESL_TEXT="$_ESL_TEXT$(_cat "$_H" "$p")"; done
for p in $(_gate pkg); do
  if _cat "$_H" "$p" | grep -q '"eslintConfig"'; then
    _ESLINT="${_ESLINT:+$_ESLINT }$p#eslintConfig"; _ESL_TEXT="$_ESL_TEXT$(_cat "$_H" "$p")"
  fi
done
_yesno() { if printf '%s' "$_ESL_TEXT" | grep -q "$1"; then echo yes; else echo no; fi; }
_HOOKS="$(_yesno react-hooks)"

# R1: a JSX spread that follows an aria-* attribute in the same opening tag.
_R1_AWK='
function idch(c) { return index("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$)]", c) > 0 }
{
  line = $0; n = length(line); i = 1
  while (i <= n) {
    c = substr(line, i, 1)
    if (!inel) {
      if (c == "<" && i < n && index("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", substr(line, i + 1, 1)) > 0 && (!idch(prev) || word ~ /^(return|yield|await|default)$/)) {
        inel = 1; depth = 0; aria = 0; q = ""; i++; continue
      }
      if (c != " " && c != "\t") { word = (idch(c) && idch(prev)) ? word c : (idch(c) ? c : ""); prev = c }
      i++; continue
    }
    if (q != "") { if (c == "\\") { i += 2; continue } if (c == q) q = ""; i++; continue }
    if (c == "\"" || c == "\047" || c == "`") { q = c; i++; continue }
    if (c == "{") {
      depth++
      if (depth == 1 && aria && substr(line, i, 4) == "{...") {
        s = substr(line, i); if (match(s, /^\{\.\.\.[^}]*\}/)) s = substr(s, 1, RLENGTH); else s = "{...}"
        print NR "\t" s " after " aname " (line " aline ")"
      }
      i++; continue
    }
    if (c == "}") { depth--; i++; continue }
    if (depth == 0 && c == ">") { inel = 0; prev = ">"; i++; continue }
    if (depth == 0 && !aria && substr(line, i, 5) == "aria-" && (i == 1 || substr(line, i - 1, 1) ~ /[ \t]/)) {
      s = substr(line, i); match(s, /^aria-[a-z-]+/); aname = substr(s, 1, RLENGTH); aria = 1; aline = NR
    }
    i++
  }
}'

# P1: a module-level, non-exported object literal whose values read a CSS module and whose
# other uses are all index reads (type-only `typeof NAME` uses are ignored).
_P1_AWK='
function idch(c) { return index("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$", c) > 0 }
{ L[NR] = $0 }
END {
  nm = split(mods, M, " ")
  for (i = 1; i <= NR; i++) {
    if (L[i] !~ /^(const|let|var)[ \t]+[A-Za-z_$][A-Za-z0-9_$]*[^=]*=[ \t]*\{/) continue
    name = L[i]; sub(/^(const|let|var)[ \t]+/, "", name); match(name, /^[A-Za-z_$][A-Za-z0-9_$]*/); name = substr(name, 1, RLENGTH)
    depth = 0; body = ""; j = i
    do { t = L[j]; depth += gsub(/\{/, "{", t); depth -= gsub(/\}/, "}", t); body = body "\n" L[j]; j++ } while (depth > 0 && j <= NR)
    last = j - 1; mod = ""
    for (m = 1; m <= nm; m++) if (index(body, M[m] ".") || index(body, M[m] "[")) mod = M[m]
    if (mod == "") continue
    uses = 0; bad = 0
    for (k = 1; k <= NR; k++) {
      if (k >= i && k <= last) continue
      t = L[k]; off = 0
      while ((p = index(substr(t, off + 1), name)) > 0) {
        p += off; before = (p > 1) ? substr(t, p - 1, 1) : ""; after = substr(t, p + length(name), 1)
        off = p + length(name) - 1
        if (idch(before) || idch(after)) continue
        pre = substr(t, 1, p - 1); sub(/[ \t]+$/, "", pre)
        if (pre ~ /typeof$/) continue
        rest = substr(t, p + length(name)); sub(/^[ \t]+/, "", rest)
        if (substr(rest, 1, 1) == "[") uses++; else bad++
      }
    }
    if (uses > 0 && bad == 0) print i "\t" name " maps keys to " mod ".* and is only read by index"
  }
}'

: > "$_TMP/cands"
while IFS= read -r f; do
  [ -n "$f" ] || continue
  ln="$(_cat "$_H" "$f" | grep -nE '(^|[^-a-z])appearance[[:space:]]*:[[:space:]]*none' | head -n 1 | cut -d: -f1 || true)"
  [ -n "$ln" ] || continue
  _cat "$_H" "$f" | grep -q 'forced-colors' && continue
  printf 'A1\t%s\t%s\t%s\n' "$f" "$ln" "appearance: none and no forced-colors media query in the file" >> "$_TMP/cands"
done <<EOF
$(_files css)
EOF

while IFS= read -r f; do
  [ -n "$f" ] || continue
  _cat "$_H" "$f" | awk "$_R1_AWK" | while IFS="$TAB" read -r ln msg; do
    printf 'R1\t%s\t%s\t%s\n' "$f" "$ln" "$msg"
  done >> "$_TMP/cands"
done <<EOF
$(_files tsx)
EOF

: > "$_TMP/pkgaxis"
while IFS= read -r f; do
  [ -n "$f" ] || continue
  pkg="$(_nearest_pkg "$f")"
  [ -n "$pkg" ] || continue
  pub="$(awk -F "$TAB" -v p="$pkg" '$1 == p { print $2; exit }' "$_TMP/pkgaxis")"
  if [ -z "$pub" ]; then pub="$(_publishable "$pkg")"; printf '%s\t%s\n' "$pkg" "$pub" >> "$_TMP/pkgaxis"; fi
  [ "$pub" = yes ] || continue
  case "$f" in (*.tsx|*.jsx|*.ts|*.js|*.mjs|*.cjs|*.mts|*.cts) ;; (*) continue ;; esac
  mods="$(_cat "$_H" "$f" | sed -nE "s/^import[[:space:]]+([A-Za-z_\$][A-Za-z0-9_\$]*)[[:space:]]+from[[:space:]]+['\"][^'\"]+\\.module\\.(css|scss|sass|less)['\"].*/\\1/p" | tr '\n' ' ')"
  [ -n "$mods" ] || continue
  _cat "$_H" "$f" | awk -v mods="$mods" "$_P1_AWK" | while IFS="$TAB" read -r ln msg; do
    printf 'P1\t%s\t%s\t%s\n' "$f" "$ln" "$msg"
  done >> "$_TMP/cands"
done <<EOF
$(_files tsx; _files ts; _files build; _files css)
EOF
sort -u -o "$_TMP/pkgaxis" "$_TMP/pkgaxis"

: > "$_TMP/raise"; : > "$_TMP/supp"
sort -t "$TAB" -k1,1 -k2,2 -k3,3n "$_TMP/cands" | while IFS="$TAB" read -r id f ln msg; do
  by="$(_off_by "$f" "$id")"
  if [ -n "$by" ]; then printf -- '- %s %s:%s %s · off in %s\n' "$id" "$f" "$ln" "$msg" "$by" >> "$_TMP/supp"
  else printf -- '- %s %s:%s %s\n' "$id" "$f" "$ln" "$msg" >> "$_TMP/raise"; fi
done

_count() { grep -c . "$1" || true; }
_list() { if [ -s "$1" ]; then cat "$1"; else echo "- (none)"; fi; }
_or_none() { if [ -n "$1" ]; then echo "$1"; else echo "(none)"; fi; }
_words() { tr '\n' ' ' < "$1" | sed 's/ *$//'; }

case "$_KIND" in
  path) _KLABEL="path" ;; working) _KLABEL="working diff" ;; branch) _KLABEL="branch" ;;
  range) _KLABEL="revision range" ;; pr) _KLABEL="pull request" ;;
esac

printf 'Front review context · %s · %s\n' "$(basename "$(pwd)")" "$_KLABEL"

printf '\n## Target\n'
printf -- '- kind: %s\n' "$_KLABEL"
printf -- '- target: %s\n' "${_TARGET:-(working diff)}"
printf -- '- base (overlay and contract read here): %s\n' "$(_short "$_B")"
if [ "$_KIND" = pr ]; then printf -- '- head (code and gates read here): pull/%s/head %s\n' "$_PR" "$(git rev-parse --short "$_H")"
else printf -- '- head (code and gates read here): %s\n' "$(_short "$_H")"; fi
[ -z "$_MB" ] || printf -- '- merge base: %s\n' "$(git rev-parse --short "$_MB")"

printf '\n## Files (%s)\n' "$(_count "$_TMP/front")"
for spec in "css|CSS -> A, U" "tsx|TSX/JSX -> R, A, T" "test|Stories/tests -> T, U" "ts|TS/JS -> R" "build|Package/build -> P when publishable"; do
  _files "${spec%%|*}" > "$_TMP/g"
  printf '%s (%s)\n' "${spec#*|}" "$(_count "$_TMP/g")"
  sed 's/^/- /' "$_TMP/g"
done

printf '\n## Overlay (%s)\n' "$(_count "$_TMP/ov.list")"
if [ -s "$_TMP/ov.list" ]; then
  while IFS="$TAB" read -r d p i; do
    case "$d" in .|..*) scope="everything" ;; (*) scope="$d/" ;; esac
    printf -- '- %s · %s · covers %s · do not report: %s\n' "$p" "$(_short "$_B")" "$scope" "$(_or_none "$(_words "$_TMP/ov.$i.off")")"
  done < "$_TMP/ov.list"
else
  echo "- (none): no REVIEW.md covers the changed files; the base rules run alone on the default floor"
fi
printf -- '- language: %s (%s)\n' "$_LANG" "$_LANG_SRC"

printf '\n## Contract files\n'
{
  while IFS= read -r d; do p="$(_join "$d" CLAUDE.md)"; if _has "$_B" "$p"; then echo "- $p"; fi; done < "$_TMP/dirs"
  _top_dirs | while IFS= read -r d; do
    for n in $(_ls "$_B" "$(_join "$d" .claude/rules)"); do case "$n" in (*.md) echo "- $(_join "$d" .claude/rules/"$n")" ;; esac; done
    for a in docs/adr docs/adrs docs/decisions doc/adr adr adrs decisions docs/architecture/decisions; do
      if _isdir "$_B" "$(_join "$d" "$a")"; then echo "- $(_join "$d" "$a")/ (ADR folder)"; fi
    done
  done
} > "$_TMP/contract"
_list "$_TMP/contract"

printf '\n## Gates (detected from config files)\n'
if [ -n "$_ESLINT" ]; then
  printf -- '- eslint: %s (react-hooks: %s, jsx-a11y: %s)\n' "$_ESLINT" "$_HOOKS" "$(_yesno jsx-a11y)"
else echo "- eslint: (none)"; fi
_gate stylelint > "$_TMP/g"; printf -- '- stylelint: %s\n' "$(_or_none "$(_words "$_TMP/g")")"
_gate tsc > "$_TMP/g"; printf -- '- tsc: %s\n' "$(_or_none "$(_words "$_TMP/g")")"
printf -- '- axe: %s\n' "$(_or_none "$(_deps '@storybook/addon-a11y|jest-axe|vitest-axe|@axe-core/[a-z-]+|axe-playwright')")"
printf -- '- visual regression: %s\n' "$(_or_none "$(_deps 'chromatic|@chromatic-com/storybook|loki|backstopjs|reg-suit|@percy/[a-z-]+|lost-pixel|storycap|[a-z:-]*visual[a-z:-]*')")"
{ _gate size-limit; _deps 'size-limit|@size-limit/[a-z-]+'; } | grep . > "$_TMP/g" || true
printf -- '- size-limit: %s\n' "$(_or_none "$(_words "$_TMP/g")")"
_gate ci > "$_TMP/ci"
if [ -s "$_TMP/ci" ]; then
  while IFS= read -r p; do
    steps="$(_cat "$_H" "$p" | sed -nE 's/^[[:space:]]*- name:[[:space:]]*//p' | tr '\n' ';' | sed 's/;$//; s/;/; /g')"
    printf -- '- CI %s: %s\n' "$p" "$(_or_none "$steps")"
  done < "$_TMP/ci"
else echo "- CI: (none)"; fi

printf '\n## Rule switches\n'
if [ -s "$_TMP/pkgaxis" ]; then
  while IFS="$TAB" read -r pkg pub; do
    if [ "$pub" = yes ]; then printf -- '- P axis: on for %s (publishable: exports or main, not private)\n' "$pkg"
    else printf -- '- P axis: off for %s (%s)\n' "$pkg" "$pub"; fi
  done < "$_TMP/pkgaxis"
else echo "- P axis: off (no package.json above the changed files)"; fi
if [ "$_HOOKS" = yes ]; then echo "- R11: off (the ESLint config carries react-hooks)"
else echo "- R11: on (no react-hooks in the ESLint config)"; fi
while IFS="$TAB" read -r d p i; do
  [ -s "$_TMP/ov.$i.off" ] || continue
  case "$d" in .|..*) scope="" ;; (*) scope=" under $d/" ;; esac
  printf -- '- off%s: %s (%s)\n' "$scope" "$(_words "$_TMP/ov.$i.off")" "$p"
done < "$_TMP/ov.list"

printf '\n## Floor in effect\n'
while IFS="$TAB" read -r d p i; do
  _section "$_TMP/ov.$i" '^floor$' > "$_TMP/f"
  [ -s "$_TMP/f" ] || continue
  case "$d" in .|..*) printf -- '- source: %s ## Floor\n' "$p" ;; (*) printf -- '- source under %s/: %s ## Floor\n' "$d" "$p" ;; esac
  cat "$_TMP/f"
done < "$_TMP/ov.list" > "$_TMP/floor"
if [ -s "$_TMP/floor" ]; then cat "$_TMP/floor"
else
  echo "- source: default (no overlay sets a floor)"
  echo "- WCAG 2.1 AA: a failure is Blocking"
  echo "- WCAG 2.2 additions: at most Should fix"
  echo "- target size: 24x24 CSS px or the spacing exception (SC 2.5.8), never 44"
  echo "- browsers: not stated"
fi

printf '\n## Candidates (%s): raise each one, or keep it under Not checked; never drop it\n' "$(_count "$_TMP/raise")"
_list "$_TMP/raise"
printf 'Suppressed by the overlay (%s)\n' "$(_count "$_TMP/supp")"
_list "$_TMP/supp"

printf '\n## Vocabulary (%s)\n' "$_LANG"
if [ "$_LANG" = fr ]; then
  echo "Sections, dans l'ordre : Bloquant | Point d'attention | Mineur (5 au plus) | Préexistant | Hors diff"
  echo "Lignes de fin : Non vérifié : … | Conflit : … (seulement s'il y en a un)"
  echo "Dernière ligne : VERDICT: PASS | CHANGES"
else
  echo "Sections, in order: Blocking | Should fix | Minor (5 at most) | Pre-existing | Outside diff"
  echo "Closing lines: Not checked: … | Conflict: … (only when one exists)"
  echo "Last line: VERDICT: PASS | CHANGES"
fi

if [ -s "$_TMP/ov.list" ]; then
  printf '\n## Overlay text\n'
  while IFS="$TAB" read -r d p i; do
    printf -- '--- %s ---\n' "$p"
    cat "$_TMP/ov.$i"
    printf -- '--- end %s ---\n' "$p"
  done < "$_TMP/ov.list"
fi
