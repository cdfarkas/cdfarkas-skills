#!/usr/bin/env bash
#
# Deterministic half of a GDPR art. 28 data processing agreement review: extract the
# contract text, propose candidate clauses per item, list bracket placeholders, and
# render the agent's verdict file as the final table. Read-only.

set -euo pipefail
export LC_ALL=C

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REFERENCE="${_SCRIPT_DIR}/../reference.md"
_MAX_CANDIDATES=6
_WORK_DIR=""

usage() {
  cat <<USAGE
Reviews a data processing agreement (GDPR art. 28) in four deterministic steps.

Usage: $(basename "${0}") <command> <contract> [options]

Commands:
  extract <contract>                   print the contract as plain text (.md .txt .docx .pdf)
  locate <contract>                    candidate lines for every art. 28 item and risk point
  placeholders <contract>              every [bracket] placeholder left in the text
  render <verdict> --contract <file> [--lang en|fr]
                                       validate the verdict file and print the final table

Exit codes: 0 ok, 1 verdict refused, 2 usage, 3 contract unreadable.
Formats, vocabulary and verdict file: reference.md next to this script.
USAGE
}

die() {
  echo "${2}" >&2
  exit "${1}"
}

_lower_ext() {
  printf '%s' "${1##*.}" | tr 'A-Z' 'a-z'
}

_extract() {
  local file="${1}"
  local out
  [[ -f "${file}" ]] || die 3 "no such file: ${file}"
  case "$(_lower_ext "${file}")" in
    md|markdown|txt)
      out="$(tr -d '\r' < "${file}")"
      ;;
    docx)
      command -v unzip >/dev/null 2>&1 || die 3 "a .docx needs unzip; export the contract to .txt instead"
      out="$(unzip -p "${file}" word/document.xml | awk '{
        gsub(/<\/w:p>/, "\n"); gsub(/<w:br\/>/, "\n"); gsub(/<w:tab\/>/, " ");
        gsub(/<[^>]*>/, "");
        gsub(/&lt;/, "<"); gsub(/&gt;/, ">"); gsub(/&quot;/, "\""); gsub(/&apos;/, "'"'"'");
        gsub(/&amp;/, "\\&"); print }')" || die 3 "cannot read ${file} as a .docx"
      ;;
    pdf)
      command -v pdftotext >/dev/null 2>&1 || die 3 "a .pdf needs pdftotext (poppler); export the contract to .txt instead"
      out="$(pdftotext -layout -enc UTF-8 "${file}" - | tr -d '\r\f')" || die 3 "pdftotext failed on ${file}"
      ;;
    *)
      die 3 "unsupported format: ${file} (use .md, .txt, .docx or .pdf)"
      ;;
  esac
  [[ -n "$(printf '%s' "${out}" | tr -d '[:space:]')" ]] || die 3 "no text extracted from ${file} (a scanned PDF has no text layer)"
  printf '%s\n' "${out}"
}

# The vocabulary is the fenced block after the <!-- dpa-vocab --> marker in reference.md.
_vocab() {
  [[ -f "${_REFERENCE}" ]] || die 3 "missing vocabulary: ${_REFERENCE}"
  awk '/<!-- dpa-vocab -->/ { armed = 1; next }
       armed && /^```/ { if (inside) exit; inside = 1; next }
       inside && NF { print }' "${_REFERENCE}"
}

_text_to_work() {
  _WORK_DIR="$(mktemp -d)"
  trap 'rm -rf "${_WORK_DIR}"' EXIT
  _extract "${1}" > "${_WORK_DIR}/contract.txt"
  _vocab > "${_WORK_DIR}/vocab.txt"
}

_locate() {
  _text_to_work "${1}"
  awk -v max="${_MAX_CANDIDATES}" -v file="${1##*/}" '
    FNR == NR {
      n = split($0, f, / :: /)
      if (n < 5) next
      items++; id[items] = f[1]; kind[items] = f[2]; label[items] = f[3]; pat[items] = f[5]
      next
    }
    { line[FNR] = $0; low[FNR] = tolower($0); total = FNR }
    END {
      printf "Candidates · %s · %d lines · %d items\n", file, total, items
      for (i = 1; i <= items; i++) {
        printf "\n## %s · %s · %s\n", id[i], label[i], kind[i]
        hits = 0
        for (l = 1; l <= total; l++) {
          if (low[l] !~ pat[i]) continue
          hits++
          if (hits <= max) { t = line[l]; gsub(/^[ \t]+/, "", t); printf "L%d: %s\n", l, substr(t, 1, 200) }
        }
        if (hits > max) printf "(%d more)\n", hits - max
        if (hits == 0) print "none: no line matched; read the whole contract before marking it MISSING or SILENT"
      }
    }' "${_WORK_DIR}/vocab.txt" "${_WORK_DIR}/contract.txt"
}

# Prints "L<n>: [token]" per placeholder; markdown links and numeric references are skipped.
_placeholder_lines() {
  awk '{
    s = $0
    while (match(s, /\[[^]]*\]/)) {
      tok = substr(s, RSTART, RLENGTH); after = substr(s, RSTART + RLENGTH, 1)
      if (after != "(" && tok !~ /^\[[0-9]+\]$/) printf "L%d: %s\n", NR, tok
      s = substr(s, RSTART + RLENGTH)
    }
  }' "${1}"
}

_placeholders() {
  local found
  _text_to_work "${1}"
  found="$(_placeholder_lines "${_WORK_DIR}/contract.txt")"
  if [[ -z "${found}" ]]; then
    echo "Placeholders: 0"
  else
    echo "Placeholders: $(printf '%s\n' "${found}" | wc -l | tr -d ' ')"
    printf '%s\n' "${found}"
  fi
}

_render() {
  local verdict="" contract="" lang="en"
  while (( ${#} > 0 )); do
    case "${1}" in
      --contract) contract="${2:-}"; shift 2 ;;
      --lang) lang="${2:-}"; shift 2 ;;
      -*) usage >&2; die 2 "unknown option: ${1}" ;;
      *) verdict="${1}"; shift ;;
    esac
  done
  [[ -n "${verdict}" && -n "${contract}" ]] || { usage >&2; die 2 "render needs <verdict> and --contract <file>"; }
  [[ "${lang}" == "en" || "${lang}" == "fr" ]] || die 2 "--lang must be en or fr, got '${lang}'"
  [[ -f "${verdict}" ]] || die 2 "no such verdict file: ${verdict}"

  _text_to_work "${contract}"
  _placeholder_lines "${_WORK_DIR}/contract.txt" > "${_WORK_DIR}/placeholders.txt"
  tr -d '\r' < "${verdict}" > "${_WORK_DIR}/verdict.txt"

  awk -v lang="${lang}" -v file="${contract##*/}" -v today="$(date +%Y-%m-%d)" \
      -v err="${_WORK_DIR}/errors.txt" '
    function cell(s) { gsub(/\|/, "\\|", s); return s }
    function blank(s) { return s == "" || s == "-" }
    FILENAME ~ /vocab.txt$/ {
      n = split($0, f, / :: /)
      if (n < 5) next
      items++; order[items] = f[1]; kind[f[1]] = f[2]; label[f[1]] = (lang == "fr" ? f[4] : f[3])
      next
    }
    FILENAME ~ /verdict.txt$/ {
      if ($0 ~ /^[ \t]*(#|$)/) next
      n = split($0, f, / :: /)
      for (i = 1; i <= n; i++) { gsub(/^[ \t]+|[ \t]+$/, "", f[i]) }
      if (f[1] == "Q") {
        if (n != 2 || f[2] == "") { print "line " FNR ": a question is `Q :: <question>`" > err; next }
        nq++; q[nq] = f[2]; next
      }
      id = f[1]
      if (!(id in kind)) { print "line " FNR ": unknown item id `" id "`" > err; next }
      if (n != 4) { print "line " FNR ": `" id "` needs 4 fields separated by ` :: `, got " n > err; next }
      if (id in st) { print "line " FNR ": `" id "` appears twice" > err; next }
      s = f[2]; st[id] = s; ev[id] = f[3]; fx[id] = f[4]
      ok = (kind[id] == "mandatory") ? (s ~ /^(PRESENT|WEAK|MISSING)$/) : (s ~ /^(RISK|OK|SILENT)$/)
      if (!ok) print "line " FNR ": `" id "` status `" s "` is not one of " (kind[id] == "mandatory" ? "PRESENT WEAK MISSING" : "RISK OK SILENT") > err
      if (s ~ /^(PRESENT|WEAK|RISK|OK)$/ && blank(f[3])) print "line " FNR ": `" id "` is " s " but cites no evidence" > err
      if (s ~ /^(WEAK|MISSING|RISK)$/ && blank(f[4])) print "line " FNR ": `" id "` is " s " but says nothing to fix or ask" > err
      if (tolower(f[4]) ~ /compliant|conforme/) print "line " FNR ": `" id "` fix says compliant/conforme; the review lists gaps, it never certifies" > err
      next
    }
    FILENAME ~ /placeholders.txt$/ { np++; ph[np] = $0; next }
    END {
      for (i = 1; i <= items; i++) if (!(order[i] in st)) print "item `" order[i] "` has no verdict line" > err
      if (nq == 0) print "no `Q :: ` line: at least one question for a lawyer is required" > err
      close(err)
      if ((getline e < err) > 0) exit 1
      for (i = 1; i <= items; i++) {
        id = order[i]
        if (kind[id] == "mandatory") { m++; c[st[id]]++ } else if (st[id] == "RISK") r++
      }
      if (lang == "fr") {
        printf "Revue de DPA · %s · %s · %d points obligatoires : %d présents, %d faibles, %d manquants · %d points de risque\n\n", file, today, m, c["PRESENT"], c["WEAK"], c["MISSING"], r
        print "| Point | Statut | Preuve | À corriger ou à demander |"
      } else {
        printf "DPA review · %s · %s · %d mandatory: %d present, %d weak, %d missing · %d risk points\n\n", file, today, m, c["PRESENT"], c["WEAK"], c["MISSING"], r
        print "| Item | Status | Evidence | What to fix or ask |"
      }
      print "|---|---|---|---|"
      for (i = 1; i <= items; i++) {
        id = order[i]
        printf "| %s %s | %s | %s | %s |\n", id, label[id], st[id], cell(ev[id]), cell(fx[id])
      }
      printf "\n## %s (%d)\n", (lang == "fr" ? "Champs à compléter" : "Placeholders"), np
      if (np == 0) print (lang == "fr" ? "aucun" : "none")
      for (i = 1; i <= np; i++) print "- " ph[i]
      printf "\n## %s\n", (lang == "fr" ? "Questions pour un avocat" : "Questions for a lawyer")
      for (i = 1; i <= nq; i++) printf "%d. %s\n", i, q[i]
      print ""
      if (lang == "fr") print "Ce n'"'"'est pas un avis juridique : cette revue liste ce que le contrat contient, omet ou laisse faible au regard de l'"'"'article 28 du RGPD. Un avocat tranche."
      else print "Not a legal opinion: this lists what the contract contains, lacks or leaves weak against GDPR art. 28. A lawyer decides."
    }' "${_WORK_DIR}/vocab.txt" "${_WORK_DIR}/verdict.txt" "${_WORK_DIR}/placeholders.txt" > "${_WORK_DIR}/out.txt" || {
      cat "${_WORK_DIR}/errors.txt" >&2
      die 1 "verdict refused: $(wc -l < "${_WORK_DIR}/errors.txt" | tr -d ' ') problem(s) in ${verdict}"
    }
  cat "${_WORK_DIR}/out.txt"
}

_main() {
  local cmd="${1:-}"
  case "${cmd}" in
    -h|--help) usage; exit 0 ;;
    extract|locate|placeholders)
      [[ -n "${2:-}" ]] || { usage >&2; die 2 "${cmd} needs a contract file"; }
      "_${cmd}" "${2}"
      ;;
    render) shift; _render "${@}" ;;
    *) usage >&2; die 2 "unknown command: ${cmd:-none}" ;;
  esac
}

_main "${@}"
