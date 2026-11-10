---
name: a11y-runtime-audit
description: >
  Audit a rendered web page for accessibility in a headless browser — a local dev server page or
  a Storybook story iframe URL — and report WCAG 2.2 findings, each with its success criterion,
  severity and a repro step: axe-core rules plus what static review cannot see (keyboard Tab walk
  with focus order, visible focus, keyboard traps, focus hidden under sticky content, popups that
  ignore Escape or lose focus, reflow at 320 px, text spacing, reduced motion). Use when someone
  asks to check a page or component for accessibility, run an a11y or WCAG audit, test keyboard
  navigation or focus, or vérifier l'accessibilité. Needs Node and npm; installs pinned Playwright
  and axe-core on first run.
license: Apache-2.0
---

# Runtime accessibility audit

One script audits the page. Run it and relay its report. Do not re-run axe or walk the page by
hand: the script is the source of truth, and a second opinion from a manual pass is how
findings drift between runs.

## Run it

```bash
bash <skill-dir>/scripts/a11y-runtime-audit.sh <url> [--json <file>] [--wait-for <css>] [--max-tabs N] [--max-overlays N]
```

`<skill-dir>` is the directory holding this file. Map what the caller said:

| Caller says | Do |
|---|---|
| a page URL or `localhost:<port>/<path>` | pass it as `<url>` (add `http://` if missing) |
| a Storybook story | pass its iframe URL: `http://localhost:6006/iframe.html?id=<story-id>&viewMode=story` and `--wait-for "#storybook-root > *"` |
| a local `.html` file | `file://<absolute path>` |
| "I need the raw data", CI | `--json <file>` |
| a long page or many popups | raise `--max-tabs` / `--max-overlays` |

The page must already be served: the script does not start a dev server. If nothing answers,
say so and ask the caller to start it. The first run installs its pinned dependencies and the
Chromium headless shell (about a minute); later runs take seconds.

## Read the output

Relay the report as printed: the `Result:` line, the findings table, then the Needs review,
Focus order and Popups lines and the closing line about what a human must check. You may add, after
it, a short list of the fixes for the critical and serious rows, each tied to its row number.
Do not drop rows, merge them, or change a severity.

- `Result: FAIL` and exit 1 mean at least one critical or serious finding.
- `(heuristic)` rows can be false positives: say so when you relay them.
- `advisory` rows (reduced motion, WCAG AAA) never fail the run.
- `Needs review` items are not findings and not passes: a human decides.
- Exit 3 means nothing was audited: relay the last stderr line and stop. Never present an empty
  report as a pass.

Check list, severities, heuristics and their limits, and what a human must still check:
[reference.md](reference.md). Sources and versions: [sources.md](sources.md).
