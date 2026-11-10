#!/usr/bin/env bash
#
# a11y-runtime-audit: install the pinned Playwright + axe-core once into a cache directory,
# then run a11y-audit.mjs headless against one URL. All arguments are passed through.
#
# Read-only: it loads the page in a throwaway headless browser and changes nothing.

set -euo pipefail

_HERE="$(cd "$(dirname "${0}")" && pwd)"

case "${1:-}" in
  -h|--help|"")
    cat <<USAGE
Usage: $(basename "${0}") <url> [--json <file>] [--wait-for <css>] [--max-tabs N] [--max-overlays N]

  Audits the rendered page at <url> (dev server, Storybook iframe.html, file://) for WCAG 2.2 A/AA.
  First run installs Playwright and axe-core (pinned in package.json) and Chromium headless shell
  into \${A11Y_AUDIT_CACHE:-\${XDG_CACHE_HOME:-\$HOME/.cache}/a11y-runtime-audit}.
  Exit: 0 no critical/serious finding · 1 critical/serious finding · 2 usage · 3 could not audit.
USAGE
    [ -n "${1:-}" ] && exit 0 || exit 2 ;;
esac

command -v node >/dev/null 2>&1 || { echo "node is required but not found" >&2; exit 3; }
command -v npm >/dev/null 2>&1 || { echo "npm is required but not found" >&2; exit 3; }

_CACHE="${A11Y_AUDIT_CACHE:-${XDG_CACHE_HOME:-${HOME}/.cache}/a11y-runtime-audit}"
_KEY="$(cksum < "${_HERE}/package-lock.json" | cut -d' ' -f1)"
_DIR="${_CACHE}/${_KEY}"

if [ ! -f "${_DIR}/.installed" ]; then
  mkdir -p "${_DIR}"
  cp "${_HERE}/package.json" "${_HERE}/package-lock.json" "${_DIR}/"
  echo "a11y-runtime-audit: first run, installing pinned dependencies into ${_DIR}" >&2
  (cd "${_DIR}" && npm ci --no-audit --no-fund --loglevel=error >&2) \
    || { echo "npm ci failed in ${_DIR}" >&2; exit 3; }
  (cd "${_DIR}" && npx --no-install playwright install --only-shell chromium >&2) \
    || { echo "playwright could not install Chromium headless shell" >&2; exit 3; }
  touch "${_DIR}/.installed"
fi

cp "${_HERE}/a11y-audit.mjs" "${_HERE}/wcag22.json" "${_DIR}/"
exec node "${_DIR}/a11y-audit.mjs" "$@"
