# front-review — evaluation results

Method: the three prompts in `evals.json` review a **committed, self-contained fixture**,
`evals/fixtures/sample-ui-lib/`: a tiny publishable React component library with a root
`REVIEW.md` overlay, a second overlay in `src/legacy/`, ESLint, stylelint and axe declared in
`package.json`, and nothing installed, so no render can run. Each prompt was given to an agent
**with** the skill and to an agent **without** it, and both answers were graded by `grade.py`:
pure regex over the answer text, no model in the loop, so a rerun grades identically.

Run on 2026-10-31. Six isolated subagents, one per prompt and arm, all on model sonnet. In
each prompt the fixture path was replaced by a neutral copy in a temporary directory outside
any git repository, byte-identical to the committed fixture (checked with `diff -r`), so the
overlay files are there but nothing in the folder names the plants. The with-skill agents also
got a copy of `SKILL.md`, `reference.md` and `scripts/`, without `evals/` or the README. Both
arms were told not to use the Skill tool or any other `SKILL.md`. Wall-clock time and tokens
were not recorded: **not measured**.

The six answers are not committed: no skill in this repository commits its run answers, and
these carry absolute paths of the machine they ran on. Anyone can regenerate them with the
prompts above and grade them with the command at the end.

## What the fixture plants

| Rule | Where | Mechanism |
|---|---|---|
| A1 | `src/Checkbox.module.css` | `appearance: none`, checked and indeterminate drawn with `background-color` and a white SVG mark, no forced-colors path |
| R1 | `src/Input.tsx` | `{...rest}` after `aria-invalid`, while `data-invalid` sits before it: a caller's `aria-invalid={false}` contradicts the error border |
| A2 | `src/Button.module.css` | the only hover cue is a transform, reset to `none` under reduced motion |
| A3 | `src/IconButton.*` | an 18 px target whose `label` (its accessible name) is optional |
| P1 (hint) | `src/Button.tsx` | a module-level variant → CSS-module class map, in a package with `exports` and no `private` |

Must not be reported:

| What | Where | Why |
|---|---|---|
| R1 switched off | `src/legacy/OldField.tsx` | `src/legacy/REVIEW.md` lists R1 under `## Do not report` |
| X1 trap | `invalid` in `src/Input.tsx` | a boolean mirroring one ARIA state is fine |
| X7 trap | `useLayoutEffect` in `src/Checkbox.tsx` | dependency-less on purpose: a native click clears `indeterminate` without a prop change, so a dependency array would break the re-application |
| X4 trap | `src/Switch.*` | a 24 px target meets SC 2.5.8; a 44 px rule would flag it |

## Scores

| Case | With the skill | Without |
|---|---|---|
| `full-review` | 7/7 | 3/7 |
| `a11y-pass` | 6/6 | 5/6 |
| `fr-pr-style` | 7/7 | 5/7 |

Split into substance (findings and absences) and format (the skill's report shape):

| Case | With: substance | With: format | Without: substance | Without: format |
|---|---|---|---|---|
| full-review | 6/6 | 1/1 | 3/6 | 0/1 |
| a11y-pass | 5/5 | 1/1 | 4/5 | 1/1 |
| fr-pr-style | 4/4 | 3/3 | 3/4 | 2/3 |
| **total** | **15/15** | **5/5** | **10/15** | **3/5** |

Graded by the `grade.py` in this commit. The P1 assertion is the revised one (see "P1, demoted
after the run"): under the wording the run was given, P1 had to be a finding, no arm reported
it as one, and the with-skill `full-review` scores 6/7 (substance 5/6).

**On substance the gap is modest**: 15/15 against 10/15. The baselines found the forced-colors
defect and the undersized icon button in every case where they were asked for, respected both
overlays, and fell into none of the traps. The skill's clearest gains are the reduced-motion
hover cue (A2), which every baseline missed, the spread-order defect reported with a line (R1),
and a report in one consistent shape with a verdict line. The baselines respected the overlay
as well as the skill did on this fixture, so the overlay handling is not a measured gain here.

## What the baselines got wrong

- **A2, missed by all three.** The `full-review` baseline wrote that reduced motion "is handled
  correctly", and the `a11y-pass` baseline listed the Button's reduced-motion block under
  "Verified OK". Both read the block that removes the hover transform as correct, without
  noticing that the transform is the only hover cue. The French baseline did not raise it.
- **R1.** The `full-review` baseline missed it: it noted only the reverse mismatch (a caller
  passing `aria-invalid` alone gets no red border), with no spread and no line. The French
  baseline did report the spread after `aria-invalid`, as a nit, citing `Input.tsx` without a
  line number, so the assertion (which requires one) fails; read it as a near miss. The
  `a11y-pass` baseline mentioned it in passing inside another finding; that case does not
  assert R1.
- **P1.** No arm reported it as a finding. The `full-review` baseline judged bundle size "not a
  concern". All three with-skill runs left it on the Not checked line with a reason, judging
  the cost negligible or unmeasurable without a build: the map lives in the only module that
  uses it.
- **Format.** No baseline ended with a `VERDICT:` line. The `a11y-pass` and French baselines
  closed with a `## Not checked` / `## Non vérifié` section, which the grader credits; the
  French one also used a `## Bloquant` heading on its own.

## What the baselines found that the fixture did not plant

The baselines were not weak reviewers. Real problems in the fixture that no assertion grades:

- **No build, no types, no `dist`.** `main`, `exports` and `files` point into `dist/`, nothing
  produces it, and there is no `types` entry: `npm publish` would ship an empty, untyped package.
  The `full-review` baseline made it Blocking, the French one a Should fix. The with-skill
  `full-review` (Blocking) and French run (Point d'attention) found it too.
- **IconButton's accessible name overwritten.** `aria-label={label}` comes after `{...rest}`, so
  a caller's `aria-label` is replaced by `undefined` when `label` is omitted. Two baselines and
  all three with-skill runs reported the overwrite; the French baseline reported only that the
  optional `label` allows an unnamed button.
- **No disabled styling** on Button and Switch (IconButton too, in some answers). All three
  baselines and all three with-skill runs reported it.
- **No test environment.** `Switch.test.tsx` renders with Testing Library but no `jsdom` or
  `happy-dom` is configured. The `full-review` and French baselines reported it; of the
  with-skill runs, only `full-review` did.
- Others, from one arm or both: the invalid border growing the input by 2 px, the Checkbox
  dropping a caller's `ref`, hover lost in forced colors on IconButton and Switch, missing CSS
  module type declarations, a stylelint class-name rule the gate would trip.

## Grader history

The grader was fixed twice before this run was graded, and its regexes were tuned after reading
the six answers:

1. The first version credited only the skill's vocabulary: rule ids, section names, `path:line`.
   It was rewritten to credit the mechanism in plain English or French and to score format
   apart (commit `5c016f7`).
2. That version still graded the baselines 0/7, 0/6, 1/7 and the skill 7/7, 5/6, 7/7, and both
   numbers were artefacts. It recognised only `path:12`, so a baseline citing `Checkbox.module.css`
   "lines 17-25" or "lignes 17 à 25" earned nothing; it matched mentions inside Not checked
   lines and "What is good" sections as findings, which credited the with-skill P1 from its Not
   checked line; and its Switch trap failed on any line citing `Switch.module.css`, including an
   evidence line and a legitimate forced-colors hover finding. This commit accepts every common
   citation style, strips the Not checked and "What is good / Verified OK / Not reported"
   regions before matching, fails the Switch trap only on a finding about the Switch's target
   size, and groups lines into finding units (paragraph, list item, or heading with its
   paragraph) instead of three-line windows.
3. Tuned on the answers: A2 now also needs a word of loss (no, only, none, removed, nothing…),
   because the baseline's "Reduced motion is handled correctly" line sits in a unit that cites
   `Button.module.css` with hover and reduced motion; and the Not checked format assertion
   accepts a section heading as well as a line, in the baselines' favour.

Re-checked on the hand-written samples: the ideal answer scores full marks; three empty answers
score 0 on every assertion; a plain-words answer with no rule ids, no `VERDICT` and no skill
labels scores full substance and 0 on format; an answer planting a switched-off R1, a 44 px
Switch finding and dependency-array advice fails exactly those assertions.

## Remaining biases

- `src/legacy/REVIEW.md` names the switched-off rule by the skill's own id, "R1". The skill maps
  it mechanically; a baseline has to read "legacy fields keep their prop order" (all three did).
- The root `REVIEW.md` states the 24 px floor and makes a state lost in forced colors Blocking,
  and both arms read it. A1, A3 and the Switch trap therefore test reading the overlay as much
  as anything the skill brings, which narrows the measurable gap.
- The fixture and the grader were written by the skill's author, with plants that match the
  skill's rule ids, and the grader was tuned after reading the answers (above).
- One run per prompt and arm: no variance is measured.

## P1, demoted after the run

All three with-skill runs left the script's P1 candidate on the Not checked line, judging its
consumer cost negligible or unmeasurable without a build. That is a fair call, and it contradicted the skill's rule
that a script candidate is never dropped. After the run, P1 became a **hint**: the script now
prints it under `## Hints`, not `## Candidates`, and `SKILL.md` and `reference.md` say to report
it or name it on the Not checked line with a reason. A1 and R1 stay mandatory candidates. The
P1 assertion changed to match: "P1 is either reported as a finding or listed in Not checked
with a reason".

**This change came after the run.** The run measured the previous wording: the with-skill
agents saw P1 under `## Candidates (3)` with "never drop it". The assertion counts did not
change.

## Runs not completed

None. All six answers were produced and graded.

## Reproducing

```bash
# from the repo root: the script half
bash skills/front-review/scripts/front-review.sh skills/front-review/evals/fixtures/sample-ui-lib
```

Graded answers go in a run directory as `full-review.md`, `a11y-pass.md` and `fr-pr-style.md`,
then `python3 skills/front-review/evals/grade.py <run-dir>`; exit code 0 means every assertion
passed. On Windows, set `PYTHONUTF8=1`.
