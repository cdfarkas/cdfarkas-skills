# a11y-runtime-audit — evaluation results

Method: the three prompts in `evals.json` were each given to an agent **with** the skill and to
an agent **without** it, in isolated sessions (general-purpose subagents, model sonnet), following
the `skill-creator` with/without protocol. Both arms got the same URL. The pages were served from a
neutral copy of `evals/fixtures/` (`python3 -m http.server 8765`), so the baselines could not read
the fixture folder or this skill. Both arms had a shell, Node and Playwright available and were told
to keep any browser headless. Answers were graded by `grade.py`: regex over the answer text, no
model in the loop.

Run on 2026-11-10 with axe-core 4.14.0, `@axe-core/playwright` 4.14.0, Playwright 1.65.0 and
Chromium headless shell 158.0.8127.18 on macOS, Node 24. The script alone takes about 8 s on
`broken.html` once its dependencies are cached, and its Markdown output was byte-identical over
three consecutive runs.

## What the fixtures plant

| Planted in `broken.html` | Expected finding |
|---|---|
| icon-only `<button>` with no name | `axe/button-name`, 4.1.2 |
| `#b5b5b5` text on white | `axe/color-contrast`, 1.4.3 |
| two adjacent 14×14 px buttons | `axe/target-size`, 2.5.8 |
| `<div onclick>` "Save" | `pointer-only`, 2.1.1 |
| `.nofocus:focus { outline: none }` on "Help" | `focus-visible`, 2.4.7 |
| link positioned under a fixed cookie bar | `focus-obscured`, 2.4.11 |
| 640 px fixed-width banner | `reflow-320`, 1.4.10 |
| 20 px high `overflow: hidden` badge | `text-spacing`, 1.4.12 (heuristic) |
| infinite CSS animation, no reduced-motion query | `reduced-motion`, 2.3.3 (advisory) |
| `role="dialog"` that ignores Escape | `overlay-escape` (APG) |
| menu whose Escape hides it with focus inside | `overlay-focus-return`, 2.4.3 |

`clean.html` has the same content done right: a named button, a real `<button>`, AA contrast,
32 px targets, a native `<dialog>` opened with `showModal()`, a menu that refocuses its trigger,
a fluid banner, and the animation inside `prefers-reduced-motion: no-preference`. It must produce
no critical or serious finding.

## Scores

| Case | With the skill | Without |
|---|---|---|
| `broken-findings` | 8/8 | 4/8 |
| `keyboard-popups` | 5/5 | 2/5 |
| `clean-control` | 5/5 | 5/5 |

| Arm | Wall-clock per case | Tokens per case |
|---|---|---|
| With the skill | 56.6 s, 32.2 s, 30.7 s (mean 39.8 s) | 78.4k, 78.4k, 75.0k (mean 77.3k) |
| Without | 88.9 s, 45.2 s, 79.6 s (mean 71.2 s) | 78.7k, 76.2k, 74.5k (mean 76.4k) |

Every run completed; nothing is reported as not measured.

## What the scores do and do not mean

Read plainly, **the baselines did not fail at detection.** The `broken-findings` baseline ran
axe-core 4.14 itself, walked the page with the keyboard in headless Chromium, measured reflow at
320 px, and found every planted failure except the text-spacing one, which it flagged as
"likely, unverified". It also found real problems the script does not check (see below). Its 4/8
comes from not naming axe rule ids and not linking any Understanding page: its table cites the SC
number and a description.

The gap the skill closes is **traceability and repeatability**, not discovery:

- every finding carries the axe rule id or check id, the SC linked to its Understanding page, a
  severity from a fixed scale and a repro step, so a reader can re-run or dispute each row;
- the focus order is printed as numbered Tab stops, which the human reading-order check needs;
- `FAIL` / `PASS` and an exit code a CI job can gate on;
- the same output on every run. Without the skill each agent chose its own checks, columns and
  severity words. The clean-page baseline did not report on reflow or text spacing at all;
- 44 % less wall-clock per case on average, for the same token count.

`clean-control` does not discriminate: both arms correctly said the page passes. It is kept as
the false-positive guard. The script raises nothing critical or serious on the clean page, which is
what the assertion checks.

## Grader defects the run exposed

The first grading pass scored the baselines lower than the final table, because three assertions
required the skill's exact wording. All three were fixed in `grade.py` before the scores above, and
both arms were regraded with the fixed grader:

1. "the dialog stays open on Escape" accepted only `stays open` / `does not close` on the same line
   as the trigger. The baseline wrote "Escape does nothing" one line below "Settings dialog". It
   now matches within a 400-character window, and accepts `does nothing`, `still open`,
   `remains open` and `ignored`.
2. The Enter-then-Escape repro check needed both keys on one line. It now uses the same window.
3. On the clean page, "passes" accepted only `PASS` / `no critical or serious`, and the dialog had
   to be named `#open-modal`. "No WCAG violations", "nothing blocks" and "Open settings" / "dialog"
   now count.

## What the baselines found that the script does not

These are real keyboard problems in `broken.html` that the script misses:

- **The modal does not contain focus.** Tab from the dialog's Close button reaches the page behind
  an `aria-modal="true"` dialog. The script only opens the popup and presses Escape; it does not
  Tab inside it.
- **Menu keyboard support.** The menu has no arrow-key navigation, Enter and Space do nothing on
  a menu item, and Tab leaves the menu open. That is APG guidance more than a WCAG failure, but
  a reviewer wants to know.

Both are candidates for a next version: a Tab-inside-the-modal check is a few lines on top of the
popup loop. They are not added here because the eval would have to grow with them.

## Reproducing

```bash
cd skills/a11y-runtime-audit/evals/fixtures && python3 -m http.server 8765 &
# produce one answer file per case (broken-findings.md, keyboard-popups.md, clean-control.md)
python3 skills/a11y-runtime-audit/evals/grade.py <run-dir>
```

The script's own output passes every assertion: put the `broken.html` report in
`broken-findings.md` and `keyboard-popups.md`, and the `clean.html` report in `clean-control.md`.
Exit code 0 means every assertion passed. The recorded answers are not committed; the fixtures and
the grader are, so the run can be repeated against a new axe-core or Playwright version (see
`reference.md`, "Updating").
