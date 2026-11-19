#!/usr/bin/env bash
#
# French AIPD / GDPR DPIA helper: requirement check, risk placement on the CNIL scales,
# and a draft in the CNIL PIA structure. Reads one answers file; writes to stdout, or the
# draft to the file given with render --out.

set -euo pipefail

usage() {
  cat <<USAGE
Checks whether a French AIPD / GDPR DPIA (art. 35) is required and drafts it in the CNIL
PIA structure. Never validates anything: every verdict ends with "to confirm with the DPO".

Usage: $(basename "${0}") <command> [args]

Commands:
  init                         print a blank answers file (every answer "unknown")
  check  <answers-file>        criteria count (EDPB WP248 / CNIL 2018-326), CNIL list
                               (deliberation 2018-327) and the verdict line
  risk   <severity> <likelihood>
                               place one risk on the CNIL 4-level scales (1-4 or label)
  render <answers-file> [--out <draft.md>]
                               the DPIA draft in markdown, TODO for every unknown fact;
                               with --out, write it there and print the summary to relay
  -h, --help                   show this help

Answers file: one "key: value" per line, "#" starts a comment. Criteria and list items take
"yes | <fact from the project>", "no | <why>" or "unknown". Run "init" for every key.
USAGE
}

die() { printf 'fr-dpia: %s\n' "$*" >&2; exit 2; }

CRITERIA="1|evaluation or scoring, including profiling|évaluation/scoring (y compris le profilage)
2|automated decision-making with legal or similar significant effect|prise de décision automatisée avec un effet juridique ou similaire
3|systematic monitoring|surveillance systématique de personnes
4|sensitive data or data of a highly personal nature|données sensibles
5|data processed on a large scale|données traitées à grande échelle
6|matching or combining datasets|croisement ou combinaison de données
7|data concerning vulnerable data subjects|données concernant des personnes vulnérables (patients, personnes âgées, enfants, etc.)
8|innovative use or new technological or organisational solutions|utilisation innovante ou application de nouvelles solutions technologiques ou organisationnelles
9|processing that prevents exercising a right or using a service or contract|traitement pouvant exclure du bénéfice d'un droit, d'un service ou d'un contrat"

CNIL_LIST="1|Traitements de données de santé mis en œuvre par les établissements de santé ou les établissements médico-sociaux pour la prise en charge des personnes
2|Traitements portant sur des données génétiques de personnes dites « vulnérables » (patients, employés, enfants, etc.)
3|Traitements établissant des profils de personnes physiques à des fins de gestion des ressources humaines
4|Traitements ayant pour finalité de surveiller de manière constante l'activité des employés concernés
5|Traitements ayant pour finalité la gestion des alertes et des signalements en matière sociale et sanitaire
6|Traitements ayant pour finalité la gestion des alertes et des signalements en matière professionnelle
7|Traitements des données de santé nécessaires à la constitution d'un entrepôt de données ou d'un registre
8|Traitements impliquant le profilage des personnes pouvant aboutir à leur exclusion du bénéfice d'un contrat ou à la suspension voire à la rupture de celui-ci
9|Traitements mutualisés de manquements contractuels constatés, susceptibles d'aboutir à une décision d'exclusion ou de suspension du bénéfice d'un contrat
10|Traitements de profilage faisant appel à des données provenant de sources externes
11|Traitements de données biométriques aux fins de reconnaissance des personnes parmi lesquelles figurent des personnes dites « vulnérables »
12|Instruction des demandes et gestion des logements sociaux
13|Traitements ayant pour finalité l'accompagnement social ou médico-social des personnes
14|Traitements de données de localisation à large échelle"

FIELDS="title|What is the processing called?
controller|Who is the controller (responsable de traitement)?
dpo|Has a DPO been designated, and who gives the advice required by art. 35(2)?
purposes|What are the purposes — determined, explicit and legitimate (art. 5.1.b)?
benefits|What benefits are expected, for the organisation, the data subjects and society?
standards|Which codes of conduct, certifications or sector rules apply (art. 40, 42)?
processors|Which processors take part, under which contract (art. 28)?
data_subjects|Who are the data subjects?
data|Which personal data are processed, by category?
recipients|Who receives the data, and why do they need them?
retention|How long is each category kept (art. 5.1.e)?
lifecycle|How do the data flow, from collection to erasure?
supports|On which supports do the data live (applications, hosting, devices, paper)?
legal_basis|What is the lawful basis (art. 6), and the art. 9 condition for special categories?
minimisation|Why is each data item adequate, relevant and limited (art. 5.1.c)?
accuracy|How are the data kept accurate and up to date (art. 5.1.d)?
information|How are data subjects informed (art. 12 to 14)?
consent|Is consent collected — demonstrable, withdrawable (art. 7, 8)? If not, why not?
access_portability|How are the rights of access and portability exercised (art. 15, 20)?
rectification_erasure|How are the rights to rectification and erasure exercised (art. 16, 17)?
restriction_objection|How are the rights to restriction and objection exercised (art. 18, 21)?
transfers|Are data transferred outside the EU, and under which safeguard (art. 44 to 49)?
measures_data|Which measures protect the data themselves (encryption, anonymisation, partitioning, access control, traceability)?
measures_system|Which general security measures apply (operations security, backups, hardware)?
measures_org|Which organisational measures apply (policy, staff, incident and breach handling, third parties)?
subjects_views|Were the views of data subjects or their representatives sought (art. 35(9))?"

EVENTS="access|Illegitimate access to data|Accès illégitime à des données
modification|Unwanted modification of data|Modification non désirée de données
disappearance|Disappearance of data|Disparition de données"

RISK_PARTS="impacts|What would the data subjects suffer if it happened?
sources|Who or what could cause it (risk sources)?
threats|How could it happen (threats on the supports)?
measures|Which existing or planned measures address it?"
R=""
TODOS=""
ART36=""
RS=0
RL=0
SEVERITY_LABELS=("TODO" "1. Négligeable" "2. Limitée" "3. Importante" "4. Maximale")
LIKELIHOOD_LABELS=("TODO" "1. Négligeable" "2. Limité" "3. Important" "4. Maximal")

shopt -s nocasematch

trim_r() {
  R="$1"
  R="${R#"${R%%[![:space:]]*}"}"
  R="${R%"${R##*[![:space:]]}"}"
}

load() {
  [ -n "${1:-}" ] || die "missing <answers-file>"
  [ -f "$1" ] || die "no such answers file: $1"
  local line key val n ev
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    trim_r "$line"; line="$R"
    case "$line" in ""|"#"*) continue ;; *:*) ;; *) continue ;; esac
    trim_r "${line%%:*}"; key="$R"
    case "$key" in ""|*[!a-z0-9_]*) continue ;; esac
    val="${line#*:}"
    case "$val" in *[[:space:]]"#"*) val="${val%%[[:space:]]#*}" ;; esac
    trim_r "$val"; val="$R"
    eval "[ -n \"\${A_${key}+x}\" ]" || printf -v "A_${key}" '%s' "$val"
  done < "$1"
  for n in 1 2 3 4 5 6 7 8 9; do status_of "c${n}"; done
  for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14; do status_of "l${n}"; done
  for ev in access modification disappearance; do risk_values "$ev"; done
}

raw() { local v="A_$1"; R="${!v-}"; }

status_of() {
  raw "$1"; trim_r "${R%%|*}"
  case "$R" in
    yes|oui) R=yes ;;
    no|non) R=no ;;
    ""|unknown|inconnu|todo|"?") R=unknown ;;
    *) die "$1: '$R' is not yes, no or unknown" ;;
  esac
}

fact_of() {
  raw "$1"
  case "$R" in *"|"*) trim_r "${R#*|}" ;; *) R="" ;; esac
}

field_or_todo() {
  raw "$1"
  case "$R" in ""|unknown|todo|inconnu|"?") R="TODO: $2" ;; esac
}

question_of() {
  local key q
  while IFS='|' read -r key q; do
    if [ "$key" = "$1" ]; then R="$q"; return 0; fi
  done <<EOF
$FIELDS
EOF
  die "no question for $1"
}

note_todo() {
  case "$R" in TODO:*) case "$TODOS" in *"- $1:"*) ;; *) TODOS="${TODOS}- $1: ${R#TODO: }
" ;; esac ;; esac
}

bullet() {
  question_of "$1"; field_or_todo "$1" "$R"; note_todo "$1"
  printf -- '- **%s**: %s\n' "$1" "$R"
}

level_num() {
  case "$1" in
    1|négligeable|negligeable|negligible) R=1 ;;
    2|limitée|limitee|limité|limite|limited) R=2 ;;
    3|importante|important|significant) R=3 ;;
    4|maximale|maximal|maximum) R=4 ;;
    ""|unknown|todo|inconnu|"?") R=0 ;;
    *) R=x ;;
  esac
}

wp248_flag() {
  if [ "$1" = 0 ] || [ "$2" = 0 ]; then R=unknown
  elif [ "$1" = 4 ] || [ "$2" = 4 ]; then R=yes
  else R=no; fi
}

risk_values() {
  raw "${1}_severity"; level_num "$R"; RS="$R"
  raw "${1}_likelihood"; level_num "$R"; RL="$R"
  [ "$RS" = x ] && die "${1}_severity: not 1-4 or a CNIL label"
  [ "$RL" = x ] && die "${1}_likelihood: not 1-4 or a CNIL label"
  return 0
}

cmd_init() {
  local n en fr label key q ev part
  echo "# fr-dpia answers. Criteria and list items: yes | <fact from the project>, no | <why>, or unknown."
  echo "# Severity and likelihood: 1-4 on the CNIL scales, or unknown. Empty or unknown text becomes a TODO."
  echo
  echo "# EDPB WP248 rev.01 / CNIL deliberation 2018-326 criteria"
  while IFS='|' read -r n en fr; do echo "c${n}: unknown    # ${en}"; done <<EOF
$CRITERIA
EOF
  echo
  echo "# CNIL list, deliberation 2018-327 (processing for which a DPIA is required)"
  while IFS='|' read -r n label; do echo "l${n}: unknown    # ${label}"; done <<EOF
$CNIL_LIST
EOF
  echo
  echo "# Context and fundamental principles"
  while IFS='|' read -r key q; do echo "${key}:    # ${q}"; done <<EOF
$FIELDS
EOF
  echo
  echo "# Risks, estimated with the existing or planned measures"
  while IFS='|' read -r ev en fr; do
    while IFS='|' read -r part q; do echo "${ev}_${part}:    # ${en}: ${q}"; done <<EOF2
$RISK_PARTS
EOF2
    echo "${ev}_severity: unknown"
    echo "${ev}_likelihood: unknown"
  done <<EOF
$EVENTS
EOF
}

print_check() {
  local yes=0 unknown=0 n en fr label st fact list_hits="" list_unknown=0 verdict reason rows=""
  while IFS='|' read -r n en fr; do
    status_of "c${n}"; st="$R"
    fact_of "c${n}"; fact="$R"
    [ "$st" = yes ] && yes=$((yes + 1))
    [ "$st" = unknown ] && unknown=$((unknown + 1))
    [ "$st" = unknown ] && [ -z "$fact" ] && fact="TODO: is this criterion met, and by which fact?"
    rows="${rows}- [${st}] ${n}. ${en}${fact:+ — ${fact}}
"
  done <<EOF
$CRITERIA
EOF
  echo "Criteria (EDPB WP248 rev.01, CNIL deliberation 2018-326): ${yes}/9 met, ${unknown} unknown"
  printf '%s' "$rows"

  while IFS='|' read -r n label; do
    status_of "l${n}"; st="$R"
    if [ "$st" = yes ]; then
      fact_of "l${n}"
      list_hits="${list_hits}- item ${n}: ${label}${R:+ — ${R}}
"
    elif [ "$st" = unknown ]; then
      list_unknown=$((list_unknown + 1))
    fi
  done <<EOF
$CNIL_LIST
EOF
  if [ -n "$list_hits" ]; then
    echo "CNIL list (deliberation 2018-327): matched"
    printf '%s' "$list_hits"
  else
    echo "CNIL list (deliberation 2018-327): no item matched, ${list_unknown} unknown"
  fi

  if [ -n "$list_hits" ]; then
    verdict="DPIA required"; reason="the processing is on the CNIL list"
  elif [ "$yes" -ge 2 ]; then
    verdict="DPIA likely"; reason="${yes} criteria met (two or more)"
  elif [ $((yes + unknown)) -ge 2 ] || [ "$list_unknown" -gt 0 ]; then
    verdict="DPIA undetermined"; reason="${unknown} criteria and ${list_unknown} list items unknown could change it"
  else
    verdict="DPIA not indicated"; reason="${yes} criterion met, none on the CNIL list"
    if [ "$yes" = 1 ]; then reason="${reason}; WP248 notes one criterion can be enough in some cases"; fi
  fi
  echo "Reason: ${reason}"
  if [ "$verdict" = "DPIA undetermined" ]; then
    echo "Verdict: ${verdict} — answer the unknowns, then confirm with the DPO"
  else
    echo "Verdict: ${verdict} — to confirm with the DPO"
  fi
}

cmd_check() {
  load "${1:-}"
  field_or_todo title "What is the processing called?"
  echo "fr-dpia check · ${R} · $(date +%Y-%m-%d)"
  echo
  print_check
}

cmd_risk() {
  [ $# -eq 2 ] || die "risk takes <severity> <likelihood>"
  local s l
  level_num "$1"; s="$R"; level_num "$2"; l="$R"
  case "$s" in 0|x) die "severity '$1' is not 1-4 or a CNIL label" ;; esac
  case "$l" in 0|x) die "likelihood '$2' is not 1-4 or a CNIL label" ;; esac
  wp248_flag "$s" "$l"
  echo "severity: ${SEVERITY_LABELS[$s]} · likelihood: ${LIKELIHOOD_LABELS[$l]} · map: G${s}/V${l} · wp248-high-residual-example: ${R}"
}

cmd_render() {
  local answers="${1:-}" out=""
  if [ "${2:-}" = "--out" ]; then
    [ -n "${3:-}" ] || die "--out takes <draft.md>"
    out="$3"
  elif [ -n "${2:-}" ]; then
    die "unknown render option: $2"
  fi
  load "$answers"
  if [ -z "$out" ]; then render_draft; return 0; fi
  mkdir -p "$(dirname "$out")" || die "cannot create the directory of $out"
  render_draft > "$out" || die "cannot write $out"
  echo "Draft written to: ${out}"
  echo
  print_check
  echo
  echo "Prior consultation (art. 36): ${ART36}"
  echo
  if [ -n "$TODOS" ]; then
    echo "TODO questions (answer them in the answers file, then run render again):"
    printf '%s' "$TODOS"
  else
    echo "TODO questions: none in the answers file; the DPO advice and the controller's decision stay open."
  fi
}

render_draft() {
  local key ev en fr part q any_yes=0 any_unknown=0 sm lm
  field_or_todo title "What is the processing called?"
  echo "# AIPD / DPIA — ${R}"
  echo
  echo "> DRAFT, not validated. Drafted with the CNIL PIA method (February 2018 edition). The"
  echo "> controller decides on validation after the DPO's advice (art. 35(2)); nothing here is a"
  echo "> legal opinion. Every TODO is a fact nobody has supplied yet: answer it, do not guess it."
  echo
  echo "Date of draft: $(date +%Y-%m-%d)"
  echo
  echo "## 0. Is a DPIA required?"
  echo
  print_check
  echo
  echo "## 1. Context (étude du contexte)"
  echo
  echo "### 1.1 Overview"
  echo
  for key in title controller dpo purposes benefits standards processors; do bullet "$key"; done
  echo
  echo "### 1.2 Data, processes and supports"
  echo
  for key in data_subjects data recipients retention lifecycle supports; do bullet "$key"; done
  echo
  echo "## 2. Fundamental principles (principes fondamentaux)"
  echo
  echo "### 2.1 Necessity and proportionality"
  echo
  for key in purposes legal_basis minimisation accuracy retention; do bullet "$key"; done
  echo
  echo "### 2.2 Rights of data subjects"
  echo
  for key in information consent access_portability rectification_erasure restriction_objection processors transfers; do bullet "$key"; done
  echo
  echo "## 3. Risks (risques liés à la sécurité des données)"
  echo
  echo "### 3.1 Existing or planned measures"
  echo
  for key in measures_data measures_system measures_org; do bullet "$key"; done
  echo
  echo "### 3.2 Risk assessment"
  echo
  echo "Severity scale: 1. Négligeable · 2. Limitée · 3. Importante · 4. Maximale."
  echo "Likelihood scale: 1. Négligeable · 2. Limité · 3. Important · 4. Maximal."
  echo "Both are estimated with the existing or planned measures (CNIL, PIA knowledge bases)."
  echo
  while IFS='|' read -r ev en fr; do
    risk_values "$ev"
    echo "#### ${en} (${fr})"
    echo
    while IFS='|' read -r part q; do
      field_or_todo "${ev}_${part}" "$q"; note_todo "${ev}_${part}"
      printf -- '- **%s**: %s\n' "$part" "$R"
    done <<EOF2
$RISK_PARTS
EOF2
    if [ "$RS" = 0 ]; then
      R="TODO: how severe would the impacts be, on the CNIL scale 1-4?"; note_todo "${ev}_severity"
      echo "- **severity**: ${R}"
    else echo "- **severity**: ${SEVERITY_LABELS[$RS]}"; fi
    if [ "$RL" = 0 ]; then
      R="TODO: how likely is it, on the CNIL scale 1-4?"; note_todo "${ev}_likelihood"
      echo "- **likelihood**: ${R}"
    else echo "- **likelihood**: ${LIKELIHOOD_LABELS[$RL]}"; fi
    echo
  done <<EOF
$EVENTS
EOF
  echo "## 4. Action plan (plan d'action)"
  echo
  echo "| Additional measure | Owner | Term | Difficulty | Cost | Progress |"
  echo "|---|---|---|---|---|---|"
  echo "| TODO: which measure would lower a risk above? | TODO | TODO: Trimestre / Année / 3 ans | TODO: Faible / Moyenne / Élevée | TODO: Nul / Moyen / Important | Non démarré |"
  echo
  echo "## 5. Residual risks and prior consultation (art. 36)"
  echo
  echo "| Risk | Severity | Likelihood | Map | Matches the WP248 high-residual-risk example |"
  echo "|---|---|---|---|---|"
  while IFS='|' read -r ev en fr; do
    risk_values "$ev"
    wp248_flag "$RS" "$RL"
    if [ "$R" = yes ]; then any_yes=1; fi
    if [ "$R" = unknown ]; then any_unknown=1; fi
    sm="$RS"; lm="$RL"
    if [ "$sm" = 0 ]; then sm="?"; fi
    if [ "$lm" = 0 ]; then lm="?"; fi
    printf '| %s | %s | %s | G%s/V%s | %s |\n' "$en" "${SEVERITY_LABELS[$RS]}" "${LIKELIHOOD_LABELS[$RL]}" "$sm" "$lm" "$R"
  done <<EOF
$EVENTS
EOF
  echo
  if [ "$any_yes" = 1 ]; then
    ART36="At least one risk sits at severity 4 or likelihood 4, the shape of the WP248 example of a high residual risk. **Question for the DPO**: once the action plan is in place, does a residual risk remain high, so that the CNIL must be consulted before the processing starts (art. 36(1))?"
  elif [ "$any_unknown" = 1 ]; then
    ART36="**Question for the DPO**: prior consultation (art. 36(1)) cannot be assessed until every severity and likelihood in section 3.2 is estimated."
  else
    ART36="No risk sits at severity 4 or likelihood 4. **Question for the DPO**: does any residual risk still remain high, so that the CNIL must be consulted before the processing starts (art. 36(1))?"
  fi
  echo "$ART36"
  echo
  echo "## 6. Validation"
  echo
  echo "- **DPO advice (art. 35(2))**: TODO: the DPO's written advice and its date."
  question_of subjects_views; field_or_todo subjects_views "$R"; note_todo subjects_views
  echo "- **Views of data subjects (art. 35(9))**: ${R}"
  echo "- **Controller's decision**: TODO: the controller's decision (validate, improve or refuse) and its justification. Not taken in this draft."
  echo "- **Review**: the CNIL asks for a review at least every three years, and on any significant change."
}

case "${1:-}" in
  init) cmd_init ;;
  check) shift; cmd_check "$@" ;;
  risk) shift; cmd_risk "$@" ;;
  render) shift; cmd_render "$@" ;;
  -h|--help) usage ;;
  "") usage >&2; exit 2 ;;
  *) usage >&2; die "unknown command: $1" ;;
esac
