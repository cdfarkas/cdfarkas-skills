# a11y-runtime-audit

An accessibility audit of the **rendered** page, in headless Chromium: a local dev server page or
a Storybook story. It runs axe-core for WCAG 2.2 A/AA, then does what static code review cannot:
walks the page with Tab, opens every declared popup and presses Escape, reflows it at 320 px,
applies the text-spacing overrides and turns on reduced motion. Every finding carries its WCAG 2.2
success criterion, linked to the Understanding page, a severity, and a repro step.

```
a11y-runtime-audit · http://localhost:8765/broken.html · 2026-11-10 · axe-core 4.14.0 · Playwright 1.65.0 · Chromium headless 1280x800

Result: FAIL · 1 critical, 6 serious, 3 moderate, 0 minor, 1 advisory

| # | Severity | WCAG 2.2 | Check | Element | Repro |
|---|---|---|---|---|---|
| 1 | critical | [4.1.2 Name, Role, Value (A)](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html) | axe/button-name | `.icon` | Open the URL and inspect `.icon`: Element does not have inner text that is visible to screen readers |
| 5 | serious | [2.4.11 Focus Not Obscured (Minimum) (AA)](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) | focus-obscured | `body > a.under-cookie` | Open the URL, press Tab 2 times: `body > a.under-cookie` is focused but hidden under `body > div.cookie`. |
| 8 | moderate | [APG](https://www.w3.org/WAI/ARIA/apg/patterns/) | overlay-escape | `#open-modal` | Open the URL, focus `#open-modal`, press Enter, then Escape: the popup stays open. |
…

Focus order (8 of 8 tabbable, walk ended: left-page): 1. `body > div.cookie > a` "Read the policy" · 2. …
Popups tested: `#open-modal` stays open on Escape · `#actions` closes on Escape, focus lands on #actions-menu > li:nth-of-type(1)
```

## Usage

```
bash scripts/a11y-runtime-audit.sh <url> [--json <file>] [--wait-for <css>] [--max-tabs N] [--max-overlays N]
```

For a Storybook story, pass `iframe.html?id=<story-id>&viewMode=story` and
`--wait-for "#storybook-root > *"`. Exit 0 means no critical or serious finding, 1 means at least
one, 3 means the page could not be audited. Needs Node and npm: the first run installs the pinned
Playwright 1.65.0, `@axe-core/playwright` 4.14.0 and axe-core 4.14.0 into a cache directory, plus
Chromium headless shell; nothing goes into the audited project.

Checks, severities, which ones are heuristic, and what a human must still do (a screen-reader
pass, meaningful alt text, reading order): [`reference.md`](reference.md). Sources and the
versions they were read at: [`sources.md`](sources.md).

## Evaluation

Run against two committed fixture pages, one deliberately broken and one clean control: 8/8, 5/5
and 5/5 with the skill, 4/8, 2/5 and 5/5 without. The baselines found most issues too; the gap is
rule ids, linked criteria, repro steps and a repeatable result. Method and caveats in
[`evals/RESULTS.md`](evals/RESULTS.md).
