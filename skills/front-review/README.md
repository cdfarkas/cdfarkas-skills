# front-review

A front-end code review for any React, TypeScript and CSS stack, tuned per repo by a
`REVIEW.md` overlay. A script resolves the target and prints a deterministic review context;
the skill applies the judgement rules on top, verifies each finding against the code and prints
a fix list with a verdict. It never posts to GitHub.

## Usage

```bash
bash skills/front-review/scripts/front-review.sh [<target>] [--lang en|fr]
```

- `<target>`: a path (every front file under it, reviewed as new), a branch, a revision range
  (`main..feature`), a pull request number or URL (needs `gh`), or nothing for the working diff
  against the merge base with the default branch.
- `--lang`: the report language when the overlay sets none.

Needs `git`, and `gh` for a pull request target. Read-only: a pull request head is fetched
into the object store, never checked out.

In an agent, ask for it in plain words: "review my changes", "review PR 42", "do an a11y
pass on src/components/Checkbox", "fais une revue front de cette branche".

## The overlay

Each repo adds its own requirements in a `REVIEW.md` at its root, and optionally one per
subdirectory: `## Floor`, `## Always check`, `## What Blocking means here`, `## Do not report`
(base rule ids switched off, such as `P*` for an unpublished package), `## Gates`,
`## Decisions`, `## Language`. It is read from the base branch, so a pull request cannot relax
its own review. Format and example: [reference.md](reference.md).

## Sample output

The script on the committed fixture, abridged:

```
Front review context · sample-ui-lib · path

## Files (15)
CSS -> A, U (6)
- src/Button.module.css
- src/Checkbox.module.css
…
TSX/JSX -> R, A, T (6)
- src/Input.tsx
- src/legacy/OldField.tsx
…

## Overlay (2)
- REVIEW.md · working tree · covers everything · do not report: U4
- src/legacy/REVIEW.md · working tree · covers src/legacy/ · do not report: R1
- language: en (default)

## Gates (detected from config files)
- eslint: eslint.config.js (react-hooks: yes, jsx-a11y: no)
- stylelint: .stylelintrc.json
- axe: @storybook/addon-a11y
…

## Rule switches
- P axis: on for package.json (publishable: exports or main, not private)
- R11: off (the ESLint config carries react-hooks)

## Candidates (2): raise each one, or keep it under Not checked; never drop it
- A1 src/Checkbox.module.css:8 appearance: none and no forced-colors media query in the file
- R1 src/Input.tsx:14 {...rest} after aria-invalid (line 13)
Suppressed by the overlay (1)
- R1 src/legacy/OldField.tsx:8 {...props} after aria-describedby (line 8) · off in src/legacy/REVIEW.md

## Hints (1): report each one, or name it under Not checked with a reason
- P1 src/Button.tsx:4 sizeClass maps keys to styles.* and is only read by index

## Vocabulary (en)
Sections, in order: Blocking | Should fix | Minor (5 at most) | Pre-existing | Outside diff
Closing lines: Not checked: … | Conflict: … (only when one exists)
Last line: VERDICT: PASS | CHANGES
```

The review the agent prints from it, one finding shown:

```
# Review: skills/front-review/evals/fixtures/sample-ui-lib
working tree ← working tree · overlay: REVIEW.md, src/legacy/REVIEW.md · floor: REVIEW.md ## Floor

## Blocking

`src/Checkbox.module.css:8` — PLAUSIBLE — A1
`.box` sets `appearance: none` and draws checked and indeterminate with background colour and a white SVG mark; no forced-colors path.
Failure scenario: in Windows High Contrast the three states look the same.
Evidence: src/Checkbox.module.css:8, :17-25. Not rendered (nothing installed).
Fix: an `@media (forced-colors: active)` block with system colours for both states.

Not checked: renders (nothing installed): forced colors, reduced motion, hover, 320 px, 200 % text.
VERDICT: CHANGES
```

Rules (accessibility beyond axe, React/TS, UX, library performance, tests), the noise list,
the default floor and the report template: [reference.md](reference.md).

## Evaluation

Three prompts review a committed fixture (`evals/fixtures/sample-ui-lib/`) that plants five
defects, one defect its overlay switches off, and three traps a keyword-matching reviewer
reports. The grader credits a finding by its `file:line` and mechanism, not by the skill's rule
ids, and scores substance and format apart, so a baseline is not failed on vocabulary.

Run on 2026-10-31 with `skill-creator`: 3 runs per arm on each prompt, on Opus 5.5, graded blind.
Pass rate 100% with the skill against 66% ± 22% without. Per prompt, the baselines scored 3/7 (three
runs), 5/6 (three runs) and 3/7, 6/7, 6/7. The skill costs about +135 s and +26k tokens per review.
What it adds is the reduced-motion hover cue (missed by every baseline), the spread-order defect and a
consistent report shape; the baselines respected the overlay and the traps as well as the skill did,
and found more real issues outside the planted list. The skill under-triggers: it rarely loads on its
own (2/30 and 4/30 should-trigger runs, no false trigger), and `skill-creator`'s description
optimizer found no better description in 5 iterations, so invoke it explicitly. Details:
[`evals/RESULTS.md`](evals/RESULTS.md).
