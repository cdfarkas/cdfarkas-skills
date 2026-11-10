# a11y-runtime-audit — full reference

## What runs, in order

Every check runs in one headless Chromium (Playwright's headless shell, never headed), on the
rendered page, at 1280×800 unless stated.

| Check id | WCAG 2.2 | Severity | How | Confidence |
|---|---|---|---|---|
| `axe/<rule>` | from the rule's `wcagNNN` tag | axe `impact` | `@axe-core/playwright` with tags `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa`; one row per rule, first node plus `(+N more)`. `target-size` (2.5.8) comes from here, with axe's spacing exception | axe's own |
| `pointer-only` | 2.1.1 Keyboard (A) | serious with a DOM `onclick` handler, moderate (heuristic) on `cursor: pointer` alone | non-focusable, non-native element that has an `onclick` property, or is the outermost element with `cursor: pointer` | see limits |
| `keyboard-trap` | 2.1.2 No Keyboard Trap (A) | critical | Tab walk: focus stays on one element for 2 presses, or loops before reaching every tabbable element and the loop is not inside `aria-modal` / `dialog:modal` | high |
| `focus-visible` | 2.4.7 Focus Visible (AA) | serious | during the Tab walk, the focused element's computed outline, box-shadow, border, background, colour and underline, on itself, its `::before` / `::after` and its parent, are compared with the same values captured before any focus | high, see limits |
| `focus-obscured` | 2.4.11 Focus Not Obscured (Minimum) (AA) | serious | `elementFromPoint` at the centre and four inset corners of the focused element: none hits the element, a descendant or an ancestor | high when it fires |
| `overlay-escape` | none: [APG](https://www.w3.org/WAI/ARIA/apg/patterns/) dialog and menu patterns | moderate | each Tab stop with `aria-haspopup`, `aria-expanded` or `popovertarget` (page reloaded each time): focus, Enter, wait up to 2 s for it to open (`aria-expanded="true"` or a new visible dialog / menu / listbox / tooltip / popover), Escape, wait up to 2 s for it to close | high |
| `overlay-focus-return` | 2.4.3 Focus Order (A) | moderate | same run: after the popup closes, focus is not on the trigger (or inside it) | high |
| `reflow-320` | 1.4.10 Reflow (AA) | serious | 320×800 viewport, reload: `scrollWidth > clientWidth`; names up to 3 outermost overflowing elements | high, see limits |
| `text-spacing` | 1.4.12 Text Spacing (AA) | moderate (heuristic) | inject the 1.4.12 values with `!important`; report text elements with `overflow: hidden/clip` that overflow only after the injection | medium |
| `reduced-motion` | 2.3.3 Animation from Interactions (AAA) | advisory, never blocking | `prefers-reduced-motion: reduce`, reload: every running animation from `document.getAnimations()` | high for "still runs" |

Severity order: `critical`, `serious`, `moderate`, `minor`, `advisory`. `(heuristic)` in the
Severity column marks a check that can produce a false positive.

## Output

stdout, Markdown, always in this order:

1. header: `a11y-runtime-audit · <url> · <date> · axe-core <v> · Playwright <v> · Chromium headless 1280x800`
2. `Result: FAIL · …` or `Result: PASS (no critical or serious finding) · …` with the count per severity
3. the findings table: `# | Severity | WCAG 2.2 | Check | Element | Repro`, worst first. The WCAG
   cell links the Understanding page; the Repro cell is a step a person can follow
4. `Needs review (axe incomplete, not counted)`: rules axe could not decide, with node counts
5. `Focus order`: every Tab stop with its selector and visible label, and how the walk ended
   (`left-page`, `wrapped`, `trapped`, `max-tabs`)
6. `Popups tested`: each trigger and what happened
7. the line naming what a human must still check

`--json <file>` writes the same data in full: every axe node, every finding's `understanding`
URL, `heuristic`, `advisory`, `help` (axe's rule page), the Tab stops and the popup results.

## Exit codes and failure lines

| Exit | Meaning | Last stderr line |
|---|---|---|
| 0 | no critical or serious finding (advisory never counts) | — |
| 1 | at least one critical or serious finding | — |
| 2 | usage error | `unknown flag: …`, `a http(s):// or file:// URL is required` |
| 3 | could not audit | `node is required but not found`, `npm ci failed in <dir>`, `playwright could not install Chromium headless shell`, `could not load <url>: <reason>`, `audit failed: <reason>` |

Exit 3 means nothing was audited. It is never a pass.

## Limits: which checks are heuristic

- **axe** finds only what its rules can decide. "Needs review" items are not counted and need a
  human look; a page that passes axe can still fail WCAG.
- **pointer-only** cannot see framework event handlers: React, Vue and Svelte attach listeners at
  the root, so a `<div onClick>` in those has no `onclick` property and is caught only when it also
  has `cursor: pointer`. A clickable element with neither is missed. A `cursor: pointer` on a
  purely decorative element is a false positive.
- **focus-visible** reports a style change, not whether the change is perceivable: a 1 px outline
  in the background colour passes. Indicators drawn by a grandparent (`:focus-within` two levels
  up) or by a sibling element are missed and reported as no indicator. Contrast of the indicator
  (1.4.11) is not measured.
- **focus-obscured** checks five points after the browser has scrolled the element into view.
  A cover that is translucent, or that leaves only a sliver uncovered between the sample points,
  can be misjudged. 2.4.11 fails only when the element is *entirely* hidden, which is what this
  reports; partial cover (2.4.12, AAA) is not checked.
- **keyboard-trap** sees only the page's own Tab order; an iframe or a plugin that captures keys
  differently is not modelled. A loop inside an open modal is legitimate and not reported.
- **popup checks** only open triggers that declare themselves (`aria-haspopup`,
  `aria-expanded`, `popovertarget`) and open on Enter. A dialog opened by an undeclared button, on
  hover, or on Space only is not tested; it is listed as `did not open on Enter` when declared.
- **reflow** at 320 px cannot tell content that legitimately needs two dimensions (data tables,
  maps, diagrams, the 1.4.10 exception) from a layout bug: read the named element. Horizontal
  content at 256 px height is not checked.
- **text-spacing** only finds clipping in `overflow: hidden/clip` boxes. Overlapping text in a
  fixed-height box with visible overflow is missed.
- **200 % zoom (1.4.4)** is not a separate check: a page that reflows at 320 px (400 % of 1280)
  rarely breaks at 640 px, and the overflow test at 640 px does not map to a 1.4.4 failure, which
  allows scrolling. Resize text in a real browser if the page uses fixed font sizes.
- One colour scheme and one viewport: dark mode, high-contrast mode, and states behind login or
  interaction other than Tab and popups are not visited. Audit each state at its own URL.

## What a human must still do

- A screen-reader pass (VoiceOver, NVDA or TalkBack) through the main task: names, roles, states
  and announcements as heard, not as computed.
- Judge alt text, labels and headings for meaning. axe checks they exist, not that they are right.
- Judge whether the reading order and the focus order printed in the report make sense for the
  content.
- Check live regions, error messages and timing (2.2.1) in the actual flow.
- Check focus indicator contrast (1.4.11) and anything the report lists under Needs review.

## Storybook

Pass the story's iframe URL, not the manager UI:
`http://localhost:6006/iframe.html?id=<story-id>&viewMode=story`, and
`--wait-for "#storybook-root > *"` so axe runs after the story renders. Each story is one URL;
loop over the stories you care about from the caller.

## Installation and cache

The first run copies `package.json` and `package-lock.json` into
`${A11Y_AUDIT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/a11y-runtime-audit}/<lockfile checksum>/`,
runs `npm ci` there and `playwright install --only-shell chromium` (the browser goes to
Playwright's shared browser cache). Later runs reuse it; a new lockfile gets a new directory.
Nothing is installed in the audited project.

Pinned (exact): `playwright` 1.65.0, `@axe-core/playwright` 4.14.0, `axe-core` 4.14.0.

## Updating

When WCAG, the APG or axe-core change:

1. `npm view playwright version`, `npm view @axe-core/playwright version`,
   `npm view axe-core version`; set the exact versions in `scripts/package.json` and regenerate
   `scripts/package-lock.json` with `npm install` in `scripts/` (then delete `scripts/node_modules`).
2. If WCAG changed, regenerate `scripts/wcag22.json` from `https://www.w3.org/WAI/WCAG22/wcag.json`
   (number → slug, name, level) and review the SC each non-axe check cites.
3. Re-run the evals (`evals/RESULTS.md`, "Reproducing"). The grader asserts axe rule ids
   (`button-name`, `color-contrast`, `target-size`), so a renamed or retagged rule fails the eval
   instead of silently disappearing.
4. Re-fetch every page in [sources.md](sources.md) and update its version and date.
5. Bump `metadata.version` in `.claude-plugin/marketplace.json`.
