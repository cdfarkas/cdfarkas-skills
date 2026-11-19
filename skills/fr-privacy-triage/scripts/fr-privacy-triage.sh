#!/usr/bin/env bash
#
# fr-privacy-triage: the deterministic half of the triage. Creates the project's decision log
# and lawyer question list, searches the log, appends a deduplicated open question or a
# validated decision, and renders the closing classification table. Never decides a point.

set -u
export LC_ALL=C

usage() {
  cat <<USAGE
Usage: $(basename "${0}") <command> [options]

Commands:
  init                         create the decision log and the question list if absent
  search <keyword>...          print the decision-log entries matching any keyword
  ask --question Q --why W --blocks B
                               append an open question under "## Added later", unless it is listed
  log --question Q --answer A --conditions C --validated-by ROLE --date YYYY-MM-DD --source S
                               append a professional's validated answer to the decision log
  table                        read "point<TAB>classification<TAB>reference" lines on stdin,
                               print the classification table

Options:
  --root DIR         project root (default: the git top level, else the current directory)
  --log PATH         decision log, relative to the root (default: docs/legal-decisions.md)
  --questions PATH   question list, relative to the root (default: docs/lawyer-questions.md)
  --dry-run          init, ask, log: print what would be written, write nothing
  -h, --help         this help
USAGE
}

die() { echo "$1" >&2; exit "${2:-1}"; }

ROOT="" LOG="docs/legal-decisions.md" QUESTIONS="docs/lawyer-questions.md" DRY=0
Q="" WHY="" BLOCKS="" ANSWER="" CONDITIONS="" VALIDATED="" DATE="" SOURCE=""
CMD="" KEYWORDS=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --dry-run) DRY=1; shift ;;
    --root|--log|--questions|--question|--why|--blocks|--answer|--conditions|--validated-by|--date|--source)
      [ $# -ge 2 ] || { usage >&2; die "missing value for $1" 2; }
      case "$1" in
        --root) ROOT="$2" ;; --log) LOG="$2" ;; --questions) QUESTIONS="$2" ;;
        --question) Q="$2" ;; --why) WHY="$2" ;; --blocks) BLOCKS="$2" ;;
        --answer) ANSWER="$2" ;; --conditions) CONDITIONS="$2" ;;
        --validated-by) VALIDATED="$2" ;; --date) DATE="$2" ;; --source) SOURCE="$2" ;;
      esac
      shift 2 ;;
    -*) usage >&2; die "unknown flag: $1" 2 ;;
    *) if [ -z "$CMD" ]; then CMD="$1"; else KEYWORDS+=("$1"); fi; shift ;;
  esac
done

[ -n "$CMD" ] || { usage >&2; die "no command given" 2; }

if [ -z "$ROOT" ]; then
  ROOT=$(git rev-parse --show-toplevel 2>&1) || ROOT=$(pwd)
fi
[ -d "$ROOT" ] || die "root is not a directory: $ROOT"
case "$LOG" in /*) LOG_PATH="$LOG" ;; *) LOG_PATH="$ROOT/$LOG" ;; esac
case "$QUESTIONS" in /*) Q_PATH="$QUESTIONS" ;; *) Q_PATH="$ROOT/$QUESTIONS" ;; esac

# Lowercase, fold French accents, keep letters and digits only: "Données ?" == "donnees".
NORM_AWK='
function norm(s) {
  s = tolower(s)
  gsub(/à|â|ä|À|Â|Ä/, "a", s); gsub(/é|è|ê|ë|É|È|Ê|Ë/, "e", s); gsub(/î|ï|Î|Ï/, "i", s)
  gsub(/ô|ö|Ô|Ö/, "o", s); gsub(/ù|û|ü|Ù|Û|Ü/, "u", s); gsub(/ç|Ç/, "c", s); gsub(/œ|Œ/, "oe", s)
  gsub(/[^a-z0-9]+/, " ", s); sub(/^ /, "", s); sub(/ $/, "", s)
  return s
}'

log_template() {
  cat <<EOF
# Legal decisions

Only answers validated in writing by a professional (lawyer, DPO, the CNIL) go here, with
the date and the source document. Official-source readings and unvalidated opinions do not.
Open questions go to \`$QUESTIONS\`; once answered and validated, they are logged here.
If the current situation differs from an entry's Conditions, the entry does not apply.

## Entry template

\`\`\`
### <short title>
- Question:
- Answer:
- Conditions: (facts the answer depends on; if any changes, the entry no longer applies)
- Validated by: (role, not name, e.g. "DPO", "lawyer specialised in health data")
- Date: YYYY-MM-DD
- Source document: (path or reference of the written answer)
\`\`\`

## Entries
EOF
}

questions_template() {
  cat <<EOF
# Questions for a lawyer / DPO

Data-protection questions this project cannot settle by itself. Each says why it matters
and which decision it blocks. Once answered in writing, the answer goes to \`$LOG\`.

## Added later
EOF
}

# insert_in_section FILE HEADING BLOCK: BLOCK goes at the end of section HEADING, created at EOF if absent.
insert_in_section() {
  local tmp="$1.tmp.$$"
  HEADING="$2" BLOCK="$3" awk '
    BEGIN { heading = ENVIRON["HEADING"]; block = ENVIRON["BLOCK"] }
    function emit() { if (!done) { if (prev != "") print ""; print block; done = 1 } }
    /^## / { if (inside) { emit(); print "" } inside = ($0 == heading) }
    { print; prev = $0 }
    END {
      if (!done && !inside) { print ""; print heading; prev = "" }
      emit()
    }' "$1" > "$tmp" && mv "$tmp" "$1"
}

cmd_init() {
  local path kind
  for kind in log questions; do
    if [ "$kind" = log ]; then path="$LOG_PATH"; else path="$Q_PATH"; fi
    if [ -f "$path" ]; then
      echo "exists: $path"
    elif [ "$DRY" = 1 ]; then
      echo "dry-run: would create $path"
    else
      mkdir -p "$(dirname "$path")" || die "cannot create $(dirname "$path")"
      if [ "$kind" = log ]; then log_template > "$path"; else questions_template > "$path"; fi
      echo "created: $path"
    fi
  done
}

cmd_search() {
  [ ${#KEYWORDS[@]} -gt 0 ] || die "search: give at least one keyword" 2
  [ -f "$LOG_PATH" ] || die "no decision log at $LOG_PATH; run init first"
  KW=$(printf '%s\n' "${KEYWORDS[@]}") awk "$NORM_AWK"'
    function field(name) { return (name in f) ? f[name] : "" }
    function flush(   i, hit, missing) {
      if (title == "") return
      hit = 0
      for (i = 1; i <= nk; i++) if (index(" " norm(text) " ", " " k[i]) > 0) hit = 1
      if (hit) {
        found++
        missing = ""
        if (field("question") == "") missing = missing ", question"
        if (field("answer") == "") missing = missing ", answer"
        if (field("conditions") == "") missing = missing ", conditions"
        if (field("validated by") == "") missing = missing ", validated by"
        if (field("date") !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) missing = missing ", date"
        if (field("source document") == "") missing = missing ", source document"
        print "entry: " title
        print "  question: " field("question")
        print "  answer: " field("answer")
        print "  conditions: " field("conditions")
        print "  validated by: " field("validated by")
        print "  date: " field("date")
        print "  source document: " field("source document")
        print "  status: " (missing == "" ? "complete" : "incomplete (missing: " substr(missing, 3) ") - not citable as SETTLED")
      }
      title = ""; text = ""; cur = ""; delete f
    }
    BEGIN { nk = split(ENVIRON["KW"], raw, "\n"); for (i = 1; i <= nk; i++) k[i] = norm(raw[i]) }
    /^```/ { fence = !fence; next }
    fence { next }
    /^#+ / { flush() }
    /^### / { title = substr($0, 5); text = title; next }
    title == "" { next }
    {
      text = text " " $0
      if (match($0, /^[-*] *[A-Za-z ]+:/)) {
        line = $0; sub(/^[-*] */, "", line)
        cur = tolower(substr(line, 1, index(line, ":") - 1))
        val = substr(line, index(line, ":") + 1); sub(/^ +/, "", val); sub(/ +$/, "", val)
        f[cur] = val
      } else if (cur != "" && $0 ~ /^[ \t]+[^ \t]/) {
        val = $0; sub(/^[ \t]+/, "", val); f[cur] = f[cur] (f[cur] == "" ? "" : " ") val
      }
    }
    END {
      flush()
      if (!found) { printf "no entry matches:"; for (i = 1; i <= nk; i++) printf " %s", raw[i]; print "" }
    }' "$LOG_PATH"
}

cmd_ask() {
  [ -n "$Q" ] && [ -n "$WHY" ] && [ -n "$BLOCKS" ] || die "ask: --question, --why and --blocks are all required" 2
  if [ -f "$Q_PATH" ]; then
    local dup
    dup=$(QTEXT="$Q" awk "$NORM_AWK"'
      BEGIN { want = norm(ENVIRON["QTEXT"]) }
      {
        line = $0
        sub(/^[ \t]*([-*+]|[0-9]+[.)]|#+)[ \t]+/, "", line)
        n = norm(line); sub(/^(q|question) /, "", n)
        if (n != "" && n == want) { print FNR ": " $0; exit }
      }' "$Q_PATH")
    [ -z "$dup" ] || { echo "duplicate: already listed at $Q_PATH:$dup"; return 0; }
  fi
  local block
  block=$(printf -- '- Q: %s\n  - Why it matters: %s\n  - Blocks: %s\n  - Added: %s' "$Q" "$WHY" "$BLOCKS" "$(date +%Y-%m-%d)")
  if [ "$DRY" = 1 ]; then
    echo "dry-run: would append to $Q_PATH under ## Added later:"
    printf '%s\n' "$block"
    return 0
  fi
  [ -f "$Q_PATH" ] || cmd_init >/dev/null
  insert_in_section "$Q_PATH" "## Added later" "$block" || die "ask: could not write $Q_PATH"
  echo "appended: $Q_PATH"
  printf '%s\n' "$block"
}

cmd_log() {
  local missing=""
  [ -n "$Q" ] || missing="$missing --question"
  [ -n "$ANSWER" ] || missing="$missing --answer"
  [ -n "$CONDITIONS" ] || missing="$missing --conditions"
  [ -n "$VALIDATED" ] || missing="$missing --validated-by"
  [ -n "$SOURCE" ] || missing="$missing --source"
  [ -z "$missing" ] || die "log: refused, a validated answer needs$missing" 2
  printf '%s' "$DATE" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || die "log: refused, --date must be YYYY-MM-DD (got '$DATE')" 2
  local block
  block=$(printf -- '### %s\n- Question: %s\n- Answer: %s\n- Conditions: %s\n- Validated by: %s\n- Date: %s\n- Source document: %s' \
    "$Q" "$Q" "$ANSWER" "$CONDITIONS" "$VALIDATED" "$DATE" "$SOURCE")
  if [ "$DRY" = 1 ]; then
    echo "dry-run: would append to $LOG_PATH under ## Entries:"
    printf '%s\n' "$block"
    return 0
  fi
  [ -f "$LOG_PATH" ] || cmd_init >/dev/null
  insert_in_section "$LOG_PATH" "## Entries" "$block" || die "log: could not write $LOG_PATH"
  echo "logged: $LOG_PATH"
  printf '%s\n' "$block"
}

cmd_table() {
  awk -F '\t' '
    function cell(s) { gsub(/\|/, "\\|", s); gsub(/^ +| +$/, "", s); return s }
    function bad(msg) { print "table: line " NR ": " msg > "/dev/stderr"; err = 1 }
    /^[ \t]*$/ { next }
    {
      if (NF != 3) { bad("expected 3 tab-separated fields, got " NF); next }
      p = cell($1); c = cell($2); r = cell($3)
      if (p == "") bad("empty point")
      if (c == "SETTLED") {
        if (r !~ /[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/) bad("SETTLED needs the decision-log entry and its date (YYYY-MM-DD)")
      } else if (c == "OFFICIAL") {
        if (r !~ /https:\/\/([a-z0-9-]+\.)*(cnil\.fr|legifrance\.gouv\.fr|esante\.gouv\.fr|edpb\.europa\.eu|eur-lex\.europa\.eu)(\/|[ )]|$)/)
          bad("OFFICIAL needs a URL on cnil.fr, legifrance.gouv.fr, esante.gouv.fr, edpb.europa.eu or eur-lex.europa.eu")
        if (r !~ /[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/) bad("OFFICIAL needs the access date (YYYY-MM-DD)")
        r = r " (official source, not validated for this project)"
      } else if (c == "OPEN") {
        if (r == "") bad("OPEN needs the question-list item it was filed as")
      } else bad("classification must be SETTLED, OFFICIAL or OPEN, got \"" c "\"")
      rows[++n] = "| " p " | " c " | " r " |"
    }
    END {
      if (!n && !err) { print "table: no rows on stdin" > "/dev/stderr"; exit 1 }
      if (err) exit 1
      print "| Point | Classification | Reference |"
      print "|---|---|---|"
      for (i = 1; i <= n; i++) print rows[i]
    }'
}

case "$CMD" in
  init) cmd_init ;;
  search) cmd_search ;;
  ask) cmd_ask ;;
  log) cmd_log ;;
  table) cmd_table ;;
  *) usage >&2; die "unknown command: $CMD" 2 ;;
esac
