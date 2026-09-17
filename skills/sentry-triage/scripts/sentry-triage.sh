#!/usr/bin/env bash
#
# Sentry triage report: every issue matching a Sentry search (default: unresolved,
# last 14 days) on one project, one row per issue with a clickable link, an impact
# score, the trend over the period, where in the code it fires and what kind of
# failure it is, then the clusters of issues that share one root cause.
#
# Raw output only — no prose. The severity ranking is computed here so that two
# agents reading the same project rank it the same way; judging how hard each fix
# is stays with the reader (see SKILL.md).
#
# Two passes:
#   1. the paginated issue list, with per-issue stats over the period
#   2. the latest event of every issue, in parallel, for the innermost in-app frame

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_JQ_PROGRAM="${_SCRIPT_DIR}/sentry-triage.jq"

_BASE_URL="${SENTRY_URL:-https://sentry.io}"
_ORG="${SENTRY_ORG:-}"
_PROJECT="${SENTRY_PROJECT:-}"
_PROJECT_ID=""
_PROJECT_SLUG=""
_ENV="${SENTRY_ENVIRONMENT:-}"
_PERIOD="14d"
_QUERY="is:unresolved"
_FORMAT="md"
_ISSUE=""
_DOCTOR=0
_TAGS="release,browser,url"
_TOKEN="${SENTRY_AUTH_TOKEN:-}"
_PARALLEL=8
_TITLE_WIDTH=60
_WORK_DIR=""

usage() {
  cat <<USAGE
Ranks the issues of a Sentry project by impact, as a raw table: clickable link, severity
score, users, events, trend, status, origin (app / vendor / network / browser), innermost
in-app frame, title — then the clusters of issues sharing one root cause.

Usage: $(basename "${0}") [<sentry issues url>] [options]
       $(basename "${0}") --issue <SHORT-ID|id> [--tags k1,k2] [options]
       $(basename "${0}") --doctor [options]

Parameters:
  <sentry issues url>   An issue-stream URL copied from Sentry; org, project, environment,
                        query and period are read from it (flags below override)
  --org <slug>          Sentry organization (default: \$SENTRY_ORG)
  --project <slug|id>   Project slug or numeric id (default: \$SENTRY_PROJECT)
  --env <name>          Environment filter (default: \$SENTRY_ENVIRONMENT, none = all)
  --period <p>          Sentry statsPeriod: 24h, 7d, 14d, 30d, 90d (default: 14d)
  --query <q>           Sentry issue search (default: 'is:unresolved')
  --format <fmt>        md (markdown table, default) or slack (mrkdwn bullet list)
  --issue <id>          Detail one issue instead: frames, top tag values, daily counts
  --tags <k1,k2>        Tag keys to break down in --issue mode (default: release,browser,url)
  --doctor              Check tools, token, scopes and access to the org / project, then exit
  -h, --help            Show this help

Auth: \$SENTRY_AUTH_TOKEN, else the token= line of ~/.sentryclirc (sentry-cli's file).
Self-hosted: set \$SENTRY_URL (default https://sentry.io). Requires bash, curl and jq —
on Windows, Git Bash (the shell Claude Code uses there) with jq from winget.

Examples:
  $(basename "${0}") "https://acme.sentry.io/issues/?environment=prod&project=123&statsPeriod=14d"
  SENTRY_ORG=acme SENTRY_PROJECT=web $(basename "${0}") --env prod --period 30d
  $(basename "${0}") --org acme --project web --issue WEB-2G --tags release,url,transaction
USAGE
}

get_opts() {
  while (( ${#} > 0 )); do
    case "${1}" in
      --org) _ORG="${2:-}"; shift 2 ;;
      --project) _PROJECT="${2:-}"; shift 2 ;;
      --env) _ENV="${2:-}"; shift 2 ;;
      --period) _PERIOD="${2:-}"; shift 2 ;;
      --query) _QUERY="${2:-}"; shift 2 ;;
      --format) _FORMAT="${2:-}"; shift 2 ;;
      --issue) _ISSUE="${2:-}"; shift 2 ;;
      --tags) _TAGS="${2:-}"; shift 2 ;;
      --doctor) _DOCTOR=1; shift ;;
      -h|--help) usage; exit 0 ;;
      http://*|https://*) _parse_url "${1}"; shift ;;
      *)
        echo "unknown argument: ${1}" >&2
        usage >&2
        exit 2
        ;;
    esac
  done

  if [[ "${_FORMAT}" != "md" && "${_FORMAT}" != "slack" ]]; then
    echo "--format must be md or slack, got '${_FORMAT}'" >&2
    exit 2
  fi
  (( _DOCTOR )) && return 0
  if [[ -z "${_ORG}" ]]; then
    echo "no organization: pass a Sentry URL, --org <slug>, or set SENTRY_ORG" >&2
    usage >&2
    exit 2
  fi
  if [[ -z "${_PROJECT}" ]]; then
    echo "no project: pass a Sentry URL, --project <slug|id>, or set SENTRY_PROJECT" >&2
    usage >&2
    exit 2
  fi
}

# Org comes from the <org>.sentry.io host or the /organizations/<org>/ path; the query
# string carries environment, project, query and statsPeriod. Later flags still win.
_parse_url() {
  local url="${1}"
  local host="${url#*://}"
  host="${host%%/*}"
  local path="${url#*://*/}"
  local qs=""
  [[ "${url}" == *\?* ]] && qs="${url#*\?}"
  qs="${qs%%#*}"

  if [[ "${host}" == *.sentry.io && "${host}" != "sentry.io" ]]; then
    _ORG="${host%%.sentry.io}"
    [[ "${_ORG}" == "us" || "${_ORG}" == "de" ]] && _ORG=""
  else
    _BASE_URL="${url%%://*}://${host}"
  fi
  if [[ "${path}" == organizations/* ]]; then
    _ORG="${path#organizations/}"
    _ORG="${_ORG%%/*}"
  fi

  local pair key value
  while IFS= read -r -d '&' pair || [[ -n "${pair}" ]]; do
    key="${pair%%=*}"
    value="$(_url_decode "${pair#*=}")"
    case "${key}" in
      project) _PROJECT="${value}" ;;
      environment) _ENV="${value}" ;;
      query) _QUERY="${value}" ;;
      statsPeriod) _PERIOD="${value}" ;;
    esac
  done <<< "${qs}&"
}

_url_decode() {
  local s="${1//+/ }"
  printf '%b' "${s//%/\\x}"
}

_install_hint() {
  case "${1}" in
    jq) echo "brew install jq · winget install jqlang.jq · apt install jq" ;;
    curl) echo "ships with macOS, Git for Windows and most Linux distributions" ;;
  esac
}

_require_tools() {
  local tool
  for tool in curl jq; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      echo "missing required tool: ${tool} ($(_install_hint "${tool}"))" >&2
      exit 1
    fi
  done
  if [[ ! -f "${_JQ_PROGRAM}" ]]; then
    echo "missing jq program: ${_JQ_PROGRAM}" >&2
    exit 1
  fi
}

_read_sentryclirc() {
  [[ -f "${HOME}/.sentryclirc" ]] || return 0
  _TOKEN="$(sed -n 's/^[[:space:]]*token[[:space:]]*=[[:space:]]*//p' "${HOME}/.sentryclirc" | head -1 | tr -d '\r')"
}

_resolve_token() {
  [[ -z "${_TOKEN}" ]] && _read_sentryclirc
  if [[ -z "${_TOKEN}" ]]; then
    echo "no Sentry token: set SENTRY_AUTH_TOKEN or put token= in ~/.sentryclirc" >&2
    exit 1
  fi
}

# One GET, body on stdout, response headers in $2 when given.
# The token travels in a curl config on stdin so it never reaches argv.
_api() {
  local path="${1}"
  local headers_out="${2:-/dev/null}"
  local body="${_WORK_DIR}/body.$$.${RANDOM}"
  local status

  status="$(curl -sS -K - -o "${body}" -D "${headers_out}" -w '%{http_code}' \
    "${_BASE_URL}/api/0${path}" <<CFG
header = "Authorization: Bearer ${_TOKEN}"
CFG
  )"
  case "${status}" in
    200) cat "${body}"; rm -f "${body}" ;;
    401) echo "Sentry rejected the token (HTTP 401) on ${path}" >&2; exit 1 ;;
    403) echo "no access to ${path} (HTTP 403) — wrong org slug, or the token lacks the scope" >&2; exit 1 ;;
    404) echo "not found on Sentry (HTTP 404): ${path} — check the org and project" >&2; exit 1 ;;
    *) echo "Sentry answered HTTP ${status} on ${path}: $(head -c 200 "${body}")" >&2; exit 1 ;;
  esac
}

# Follows the Link header (rel="next"; results="true"; cursor="...") and prints
# every page's array elements, one JSON document per line.
_api_paginate() {
  local path="${1}"
  local sep="&"
  [[ "${path}" != *\?* ]] && sep="?"
  local cursor=""
  local headers="${_WORK_DIR}/headers.$$.${RANDOM}"
  local page

  while :; do
    page="$(_api "${path}${cursor:+${sep}cursor=${cursor}}" "${headers}")"
    jq -c '.[]' <<< "${page}"
    cursor="$(sed -n 's/.*rel="next"; results="true"; cursor="\([^"]*\)".*/\1/p' "${headers}")"
    [[ -z "${cursor}" ]] && break
  done
}

_urlencode() {
  jq -rn --arg s "${1}" '$s | @uri'
}

# The issues endpoint filters by numeric id only; a slug is looked up first, and an
# id is checked to exist so a typo fails instead of reading as an empty project.
_resolve_project() {
  local found
  if [[ "${_PROJECT}" =~ ^[0-9]+$ ]]; then
    _PROJECT_ID="${_PROJECT}"
  else
    found="$(_api_paginate "/organizations/${_ORG}/projects/?query=slug:${_PROJECT}" \
      | jq -r --arg slug "${_PROJECT}" 'select(.slug == $slug) | .id' | head -1)"
    if [[ -z "${found}" ]]; then
      echo "unknown project '${_PROJECT}' in organization ${_ORG}" >&2
      exit 1
    fi
    _PROJECT_ID="${found}"
  fi
  _PROJECT_SLUG="$(_api "/organizations/${_ORG}/projects/?query=id:${_PROJECT_ID}" \
    | jq -r --arg id "${_PROJECT_ID}" '.[] | select(.id == $id) | .slug' | head -1)"
  if [[ -z "${_PROJECT_SLUG}" ]]; then
    echo "unknown project id ${_PROJECT_ID} in organization ${_ORG}" >&2
    exit 1
  fi
}

_env_param() {
  [[ -n "${_ENV}" ]] && printf '&environment=%s' "$(_urlencode "${_ENV}")"
  return 0
}

# Pass 1 — the whole issue list for the search, stats series over the same period.
_fetch_issues() {
  local group_period="auto"
  [[ "${_PERIOD}" == "24h" || "${_PERIOD}" == "14d" ]] && group_period="${_PERIOD}"

  _api_paginate "/organizations/${_ORG}/issues/?project=${_PROJECT_ID}&query=$(_urlencode "${_QUERY}")&statsPeriod=${_PERIOD}&groupStatsPeriod=${group_period}&sort=freq&limit=100$(_env_param)" \
    > "${_WORK_DIR}/issues.jsonl"
}

# Pass 2 — the latest event of one issue, reduced to what the ranking needs. An
# issue whose latest event cannot be read is kept with no frame rather than dropped.
_fetch_frames_one() {
  local id="${1}"
  local body
  if ! body="$(_api "/organizations/${_ORG}/issues/${id}/events/latest/?$(_env_param)" 2>/dev/null)"; then
    jq -cn --arg id "${id}" '{id: $id, frames: [], value: null, release: null}'
    return 0
  fi
  jq -c --arg id "${id}" '{
      id: $id,
      value: ([.entries[]? | select(.type == "exception") | .data.values[]? | .value] | first),
      frames: [.entries[]? | select(.type == "exception") | .data.values[]? | .stacktrace.frames[]?
               | {filename: (.filename // .absPath // ""), function: (.function // ""), line: .lineNo, inApp: (.inApp // false)}],
      release: ([.tags[]? | select(.key == "release") | .value] | first)
    }' <<< "${body}"
}

_fetch_frames() {
  export -f _fetch_frames_one _api _env_param _urlencode
  export _WORK_DIR _BASE_URL _ORG _ENV _TOKEN
  jq -r '.id' "${_WORK_DIR}/issues.jsonl" \
    | xargs -P "${_PARALLEL}" -I {} bash -c '_fetch_frames_one "$1"' _ {} \
    > "${_WORK_DIR}/frames.jsonl"
}

_jq_render() {
  jq -r -s \
    --arg org "${_ORG}" \
    --arg project "${_PROJECT_SLUG}" \
    --arg env "${_ENV}" \
    --arg period "${_PERIOD}" \
    --arg query "${_QUERY}" \
    --arg format "${_FORMAT}" \
    --arg mode "${1}" \
    --argjson title_width "${_TITLE_WIDTH}" \
    -f "${_JQ_PROGRAM}"
}

_render() {
  cat "${_WORK_DIR}/issues.jsonl" "${_WORK_DIR}/frames.jsonl" | _jq_render list
}

# --issue: one issue, its frames innermost first, its top tag values and daily counts.
# The short id is resolved first so a typo reads as "unknown issue", not as HTTP 400.
_detail() {
  local id="${_ISSUE}"
  local short_id issue
  if [[ "${id}" =~ ^[0-9]+$ ]]; then
    short_id="$(_api "/organizations/${_ORG}/issues/${id}/" 2>/dev/null | jq -r '.shortId' || true)"
  else
    short_id="$(_api "/organizations/${_ORG}/shortids/${id}/" 2>/dev/null | jq -r '.shortId' || true)"
  fi
  if [[ -z "${short_id}" ]]; then
    echo "unknown issue '${id}' in ${_ORG}/${_PROJECT_SLUG}" >&2
    exit 1
  fi
  issue="$(_api "/organizations/${_ORG}/issues/?project=${_PROJECT_ID}&query=$(_urlencode "issue:${short_id}")&statsPeriod=${_PERIOD}&groupStatsPeriod=auto&limit=1$(_env_param)" | jq -c '.[0] // empty')"
  if [[ -z "${issue}" ]]; then
    echo "issue ${short_id} has no event matching ${_PERIOD}${_ENV:+ in ${_ENV}} on project ${_PROJECT_SLUG}" >&2
    exit 1
  fi
  id="$(jq -r '.id' <<< "${issue}")"

  local key keys tag_params=""
  IFS=',' read -ra keys <<< "${_TAGS}"
  for key in "${keys[@]}"; do
    tag_params+="&key=$(_urlencode "${key}")"
  done

  {
    echo "${issue}"
    _fetch_frames_one "${id}"
    _api "/organizations/${_ORG}/issues/${id}/tags/?${tag_params#&}$(_env_param)" | jq -c '{tags: .}'
  } | _jq_render detail
}

# --doctor: one line per check, `ok` or `FAIL <cause>`; exits 1 on the first failure.
# The org and project checks run only when one is known, and say so otherwise.
_doctor() {
  local tool
  for tool in curl jq; do
    if command -v "${tool}" >/dev/null 2>&1; then echo "ok    ${tool}: $(command -v "${tool}")"
    else echo "FAIL  ${tool}: not installed ($(_install_hint "${tool}"))"; exit 1; fi
  done

  [[ -z "${_TOKEN}" ]] && _read_sentryclirc
  if [[ -n "${SENTRY_AUTH_TOKEN:-}" ]]; then echo "ok    token: SENTRY_AUTH_TOKEN"
  elif [[ -n "${_TOKEN}" ]]; then echo "ok    token: ~/.sentryclirc"
  else echo "FAIL  token: set SENTRY_AUTH_TOKEN or put token= in ~/.sentryclirc"; exit 1; fi
  if [[ ! -f "${_JQ_PROGRAM}" ]]; then echo "FAIL  jq program: ${_JQ_PROGRAM} missing"; exit 1; fi

  local who scopes missing=""
  who="$(_api "/")"
  echo "ok    auth: $(jq -r '.user.email // .user.username // "service token"' <<< "${who}") on ${_BASE_URL}"
  scopes="$(jq -r '.auth.scopes // [] | join(" ")' <<< "${who}")"
  for tool in org:read project:read event:read; do
    [[ " ${scopes} " == *" ${tool} "* ]] || missing+=" ${tool}"
  done
  if [[ -z "${missing}" ]]; then echo "ok    scopes: ${scopes}"
  else echo "FAIL  scopes: missing${missing} (have: ${scopes:-none})"; exit 1; fi

  if [[ -z "${_ORG}" ]]; then echo "skip  org: none given (pass a URL, --org, or SENTRY_ORG)"; return 0; fi
  _api "/organizations/${_ORG}/" >/dev/null
  echo "ok    org: ${_ORG}"

  if [[ -z "${_PROJECT}" ]]; then echo "skip  project: none given (pass a URL, --project, or SENTRY_PROJECT)"; return 0; fi
  _resolve_project
  echo "ok    project: ${_PROJECT_SLUG} (${_PROJECT_ID})"
  _api "/organizations/${_ORG}/issues/?project=${_PROJECT_ID}&limit=1&statsPeriod=24h$(_env_param)" >/dev/null
  echo "ok    issues: readable${_ENV:+ in ${_ENV}}"
}

_main() {
  get_opts "${@}"
  _WORK_DIR="$(mktemp -d)"
  trap 'rm -rf "${_WORK_DIR}"' EXIT

  if (( _DOCTOR )); then
    _doctor
    return
  fi
  _require_tools
  _resolve_token
  _resolve_project
  if [[ -n "${_ISSUE}" ]]; then
    _detail
    return
  fi
  _fetch_issues
  _fetch_frames
  _render
}

_main "${@}"
