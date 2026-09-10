#!/usr/bin/env bash
#
# PR to-do report: every open pull request in a GitHub org that a developer has
# to act on (review requested, authored, or assigned), one line per PR with a
# clickable link, its merge status and the concrete reasons it is stuck.
#
# Raw output only — no prose. Designed to be run by a developer in a terminal
# or by an automation on a developer's behalf.
#
# Two GraphQL passes, because GitHub computes `mergeable` / `mergeStateStatus`
# lazily (~7s per 25 PRs) and a search that asks for them together with reviews
# and checks times out (HTTP 502):
#   1. one paginated search per role (parallel) — cheap fields only
#   2. mergeability for the unique PR ids, in parallel batches of 25

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_JQ_PROGRAM="${_SCRIPT_DIR}/pr-todo.jq"

_ORG="${PR_TODO_ORG:-}"
_USER=""
_FORMAT="md"
_TITLE_WIDTH=60
_BATCH_SIZE=25
_RETRIES=3
_WORK_DIR=""

# Fields that are cheap to read from a search result. Mergeability is NOT here on purpose.
_PR_FIELDS='
  id number title url isDraft updatedAt reviewDecision
  repository { nameWithOwner }
  author { login }
  reviewRequests(first: 20) {
    nodes { requestedReviewer { __typename ... on User { login } ... on Team { slug } } }
  }
  latestOpinionatedReviews(first: 20) { nodes { author { login } state } }
  reviewThreads(first: 50) { totalCount nodes { isResolved } }
  commits(last: 1) {
    nodes { commit { statusCheckRollup { state contexts(first: 40) {
      nodes {
        __typename
        ... on CheckRun { name conclusion }
        ... on StatusContext { context state }
      }
    } } } }
  }'

usage() {
  cat <<USAGE
Lists the open pull requests a developer has to act on in a GitHub org, as a raw table:
clickable link, role (reviewer / author / assignee), merge status, blocking reasons, age.

Usage: $(basename "${0}") [--user <login>|@me] [--org <org>] [--format md|slack]

Parameters:
  --user <login>    GitHub login to report on (default: the authenticated gh user; @me is an alias)
  --org <org>       GitHub organization to search (default: \$PR_TODO_ORG)
  --format <fmt>    md (markdown table, default) or slack (mrkdwn bullet list)
  -h, --help        Show this help

Requires: gh (authenticated, repo scope on the org), jq.

Examples:
  $(basename "${0}") --org acme
  PR_TODO_ORG=acme $(basename "${0}")
  PR_TODO_ORG=acme $(basename "${0}") --user jdoe --format slack
USAGE
}

get_opts() {
  while (( ${#} > 0 )); do
    case "${1}" in
      --user)
        _USER="${2:-}"
        shift 2
        ;;
      --org)
        _ORG="${2:-}"
        shift 2
        ;;
      --format)
        _FORMAT="${2:-}"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
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
  if [[ -z "${_ORG}" ]]; then
    echo "no organization: pass --org <org> or set PR_TODO_ORG" >&2
    usage >&2
    exit 2
  fi
}

_require_tools() {
  local tool
  for tool in gh jq; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      echo "missing required tool: ${tool}" >&2
      exit 1
    fi
  done
  if [[ ! -f "${_JQ_PROGRAM}" ]]; then
    echo "missing jq program: ${_JQ_PROGRAM}" >&2
    exit 1
  fi
}

# Resolve @me / empty to the authenticated login, then check the login exists.
# Fails loudly when gh is not authenticated: nothing downstream can work without it.
_resolve_user() {
  if [[ -z "${_USER}" || "${_USER}" == "@me" ]]; then
    if ! _USER="$(gh api user --jq .login)"; then
      echo "gh is not authenticated (gh auth login)" >&2
      exit 1
    fi
  fi
  # A typo in --user would otherwise read as "nothing to do": GitHub search
  # silently returns zero results for a login that does not exist.
  local probe
  if ! probe="$(gh api "users/${_USER}" 2>&1 >/dev/null)"; then
    echo "unknown GitHub user: ${_USER} (${probe})" >&2
    exit 1
  fi
}

# Pass 1 — one paginated search for one role. The role is stamped on every node
# so the jq program can merge a PR matching several roles (e.g. reviewer AND
# assignee). `gh api --paginate` follows pageInfo.endCursor and emits one JSON
# document per page.
_search_role() {
  local role="${1}"
  local qualifier="${2}"
  local out="${3}"
  local query="org:${_ORG} is:pr is:open archived:false ${qualifier}:${_USER}"
  local attempt

  # GitHub intermittently answers a heavy search page with an empty body or a
  # 502; --paginate cannot resume mid-way, so the whole role is retried.
  for (( attempt = 1; attempt <= _RETRIES; attempt++ )); do
    if _search_role_once "${role}" "${query}" "${out}"; then
      return 0
    fi
    echo "search ${role}: attempt ${attempt}/${_RETRIES} failed, retrying" >&2
    sleep 2
  done
  return 1
}

_search_role_once() {
  local role="${1}"
  local query="${2}"
  local out="${3}"

  gh api graphql --paginate -f q="${query}" -f query="
    query(\$q: String!, \$endCursor: String) {
      search(type: ISSUE, first: 25, after: \$endCursor, query: \$q) {
        pageInfo { hasNextPage endCursor }
        nodes { ... on PullRequest { ${_PR_FIELDS} } }
      }
    }" \
    | jq -c --arg role "${role}" '.data.search.nodes[] | select(.url != null) | .role = $role' > "${out}"
}

# Pass 2 — mergeability for one batch of PR ids (a JSON array), via nodes(ids:).
# The body goes through --input because `gh api -F` cannot carry a list variable.
_fetch_mergeability() {
  local ids_json="${1}"
  local out="${2}"

  jq -n --argjson ids "${ids_json}" '{
      query: "query($ids: [ID!]!) { nodes(ids: $ids) { ... on PullRequest { id mergeable mergeStateStatus } } }",
      variables: { ids: $ids }
    }' \
    | gh api graphql --input - \
    | jq -c '.data.nodes[] | select(. != null)' > "${out}"
}

# Run the three role searches concurrently; any failure aborts the report
# (a partial to-do list is worse than none).
_run_searches() {
  local role
  local qualifier
  local pid
  local pids=()
  for role in reviewer author assignee; do
    case "${role}" in
      reviewer) qualifier="review-requested" ;;
      *) qualifier="${role}" ;;
    esac
    _search_role "${role}" "${qualifier}" "${_WORK_DIR}/search-${role}.jsonl" &
    pids+=("${!}")
  done
  for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
      echo "GitHub search failed for one role (user ${_USER}, org ${_ORG})" >&2
      exit 1
    fi
  done
}

# Batch the unique ids by _BATCH_SIZE and fetch every batch concurrently.
_run_mergeability() {
  local batch=0
  local pid
  local pids=()
  local ids_json

  # jq -s : unique PR ids across the three role files, chunked into JSON arrays, one per line.
  jq -s -c --argjson size "${_BATCH_SIZE}" \
    '[.[].id] | unique | . as $ids | [range(0; length; $size) as $i | $ids[$i:$i + $size]] | .[]' \
    "${_WORK_DIR}"/search-*.jsonl > "${_WORK_DIR}/batches.jsonl"

  while read -r ids_json; do
    (( batch++ )) || true
    _fetch_mergeability "${ids_json}" "${_WORK_DIR}/merge-${batch}.jsonl" &
    pids+=("${!}")
  done < "${_WORK_DIR}/batches.jsonl"

  for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
      echo "GitHub mergeability lookup failed (user ${_USER}, org ${_ORG})" >&2
      exit 1
    fi
  done
  # A user with zero PRs has no batch: keep the glob below satisfied.
  touch "${_WORK_DIR}/merge-0.jsonl"
}

_render() {
  # jq -s : slurp search nodes and mergeability records into one array; the
  #         program joins them by id, derives status / blockers, sorts, renders.
  jq -r -s \
    --arg user "${_USER}" \
    --arg org "${_ORG}" \
    --arg format "${_FORMAT}" \
    --argjson title_width "${_TITLE_WIDTH}" \
    -f "${_JQ_PROGRAM}" \
    "${_WORK_DIR}"/search-*.jsonl "${_WORK_DIR}"/merge-*.jsonl
}

_main() {
  get_opts "${@}"
  _require_tools
  _resolve_user

  _WORK_DIR="$(mktemp -d)"
  trap 'rm -rf "${_WORK_DIR}"' EXIT

  _run_searches
  _run_mergeability
  _render
}

_main "${@}"
