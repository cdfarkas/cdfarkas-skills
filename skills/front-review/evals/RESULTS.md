# front-review — evaluation results

**The with-skill versus without-skill run is not yet run.** No score is published until it is;
the root README shows `not measured yet`.

## Method (planned)

The three prompts in `evals.json` review a **committed, self-contained fixture**,
`evals/fixtures/sample-ui-lib/`: a tiny publishable React component library with a root
`REVIEW.md` overlay, a second overlay in `src/legacy/`, ESLint, stylelint and axe declared in
`package.json`, and nothing installed, so no render can run and the Not checked line must say
so. Each prompt runs twice with `skill-creator`, one isolated agent with the skill and one
without, and both answers are graded by `grade.py`: pure regex over the answer text, no model in
the loop. Baselines get a neutral copy of the fixture, so the overlay files stay but nothing
names the plants.

The grader scores substance and format apart, because an agent without the skill cannot know its
vocabulary. **Substance**: a finding counts when up to 3 consecutive lines cite the file with a
line number and either the rule id or the mechanism in plain English or French (forced colors,
the spread after `aria-invalid`, reduced motion with hover, target size, tree-shaking or bundle);
an absence assertion passes on any non-empty answer that cites a `file:line`. **Format**: the
last `VERDICT: CHANGES` line, the Not checked / Non vérifié line, the French section names. Each
case prints `substance x/y  format x/y  total x/y`; the scores table, once run, reports the
total, and the with/without gap is read on substance first.

## What the fixture plants

Defects that must be reported, each as `path:line` with its rule id:

| Rule | Where | Mechanism |
|---|---|---|
| A1 | `src/Checkbox.module.css` | `appearance: none`, checked and indeterminate drawn with `background-color` and a white SVG mark, no forced-colors path |
| R1 | `src/Input.tsx` | `{...rest}` after `aria-invalid`, while `data-invalid` sits before it: a caller's `aria-invalid={false}` contradicts the error border |
| A2 | `src/Button.module.css` | the only hover cue is a transform, reset to `none` under reduced motion |
| A3 | `src/IconButton.*` | an 18 px target whose `label` (its accessible name) is optional |
| P1 | `src/Button.tsx` | a module-level variant → CSS-module class map, in a package with `exports` and no `private` |

Must not be reported:

| What | Where | Why |
|---|---|---|
| R1 switched off | `src/legacy/OldField.tsx` | `src/legacy/REVIEW.md` lists R1 under `## Do not report` |
| X1 trap | `invalid` in `src/Input.tsx` | a boolean mirroring one ARIA state is fine |
| X7 trap | `useLayoutEffect` in `src/Checkbox.tsx` | dependency-less on purpose: a native click clears `indeterminate` without a prop change, so a dependency array would break the re-application |
| X4 trap | `src/Switch.*` | a 24 px target meets SC 2.5.8; a 44 px rule would flag it |

## Checks done so far

- The script, run on the fixture (Windows Git Bash, 2026-10-31), lists the three candidates
  `A1 src/Checkbox.module.css:8`, `P1 src/Button.tsx:4`, `R1 src/Input.tsx:14`, and puts
  `R1 src/legacy/OldField.tsx:8` under "Suppressed by the overlay". A2 and A3 are left to the
  agent's judgement on purpose: no regex tells a removed hover cue or an unnamed small target
  from a correct one.
- `grade.py` on a hand-written ideal answer scores full substance and format (6/6 + 1/1,
  5/5 + 1/1, 4/4 + 3/3); on three empty answers it scores 0 on every case (an absence assertion
  needs at least one `file:line` citation, so silence cannot pass it); on a plain-words answer
  that names each defect with `file:line` but no rule id, no `VERDICT` and no skill label, it
  scores full substance and format 0/1, 0/1, 0/3; on an answer that reports the switched-off R1,
  a 44 px Switch finding and dependency-array advice, exactly those assertions fail.

## Reproducing the script half

```bash
# from the repo root
bash skills/front-review/scripts/front-review.sh skills/front-review/evals/fixtures/sample-ui-lib
```

Graded answers go in a run directory as `full-review.md`, `a11y-pass.md` and `fr-pr-style.md`,
then `python3 skills/front-review/evals/grade.py <run-dir>`; exit code 0 means every assertion
passed.
