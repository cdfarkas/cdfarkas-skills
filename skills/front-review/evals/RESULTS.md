# front-review — evaluation results

Method: the three prompts in `evals.json` review a **committed, self-contained fixture**,
`evals/fixtures/sample-ui-lib/`: a tiny publishable React component library with a root
`REVIEW.md` overlay, a second overlay in `src/legacy/`, ESLint, stylelint and axe declared in
`package.json`, and nothing installed, so no render can run.

Run on 2026-10-31 with Anthropic's `skill-creator` skill (the `claude-plugins-official`
plugin): each of the three evals run 3 times with the skill and 3 times without, 18 runs, the
executors on Claude Opus 5.5 as independent subagents launched in parallel.

- **Isolation.** The fixture was copied to a neutral temporary folder outside the repository.
  The with-skill runs got a copy of the skill holding only `SKILL.md`, `reference.md` and
  `scripts/`: no `evals/`, no expected answers. Answers were written to neutral file names, so
  graders could not tell the arms apart. Both arms received the same harness context (the
  author's global agent instructions are injected into every subagent): equal in both arms,
  but not a clean-room setup.
- **Grading.** Blind, by three independent grader subagents following `skill-creator`'s
  `agents/grader.md`, one per eval, six anonymised answers each, every claim checked against
  the fixture. `grade.py` (regex, no model) ran as a cross-check. Aggregated with
  `skill-creator`'s `scripts/aggregate_benchmark.py`, reviewed in its eval viewer (static HTML,
  not committed).

The 18 answers are not committed: no skill in this repository commits its run answers.

## What the fixture plants

| Rule | Where | Mechanism |
|---|---|---|
| A1 | `src/Checkbox.module.css` | `appearance: none`, checked and indeterminate drawn with `background-color` and a white SVG mark, no forced-colors path |
| R1 | `src/Input.tsx` | `{...rest}` after `aria-invalid`, while `data-invalid` sits before it: a caller's `aria-invalid={false}` contradicts the error border |
| A2 | `src/Button.module.css` | the only hover cue is a transform, reset to `none` under reduced motion |
| A3 | `src/IconButton.*` | an 18 px target whose `label` (its accessible name) is optional |
| P1 (hint) | `src/Button.tsx` | a module-level variant → CSS-module class map, in a package with `exports` and no `private`: reported, or named under Not checked with a reason |

Must not be reported:

| What | Where | Why |
|---|---|---|
| R1 switched off | `src/legacy/OldField.tsx` | `src/legacy/REVIEW.md` lists R1 under `## Do not report` |
| X1 trap | `invalid` in `src/Input.tsx` | a boolean mirroring one ARIA state is fine |
| X7 trap | `useLayoutEffect` in `src/Checkbox.tsx` | dependency-less on purpose: a native click clears `indeterminate` without a prop change |
| X4 trap | `src/Switch.*` | a 24 px target meets SC 2.5.8; a 44 px rule would flag it |

## Scores

`skill-creator` aggregate, mean ± standard deviation over 9 runs per arm:

| Metric | With the skill | Without | Delta |
|---|---|---|---|
| Pass rate | 100% ± 0% | 66% ± 22% | +0.34 |
| Time | 286.5 s ± 72.3 s | 151.7 s ± 16.4 s | +134.9 s |
| Tokens | 138,465 ± 10,792 | 112,233 ± 3,188 | +26,232 |

Assertions passed per run (runs 1, 2, 3):

| Case | With the skill | Without |
|---|---|---|
| `full-review` | 7/7, 7/7, 7/7 | 3/7, 3/7, 3/7 |
| `a11y-pass` | 6/6, 6/6, 6/6 | 5/6, 5/6, 5/6 |
| `fr-pr-style` | 7/7, 7/7, 7/7 | 3/7, 6/7, 6/7 |

Earlier run, same day: one answer per case per arm on sonnet, graded by `grade.py` only after
two grader fixes; 7/7, 6/6, 7/7 with the skill against 3/7, 5/6, 5/7 without. Superseded by
the run above.

## What the baselines got wrong

- **`full-review`.** All three missed R1 (the spread after `aria-invalid` in `Input.tsx`), A2
  (the reduced-motion hover cue in `Button.module.css`) and P1 (the variant map, neither
  reported nor listed as not checked; two said bundle size was fine without measuring). None
  ended on the verdict line.
- **`a11y-pass`.** Every baseline missed A2: they called the reduced-motion block correct.
- **`fr-pr-style`.** The 3/7 run wrote "Blocking" in English, had no Non vérifié, missed R1 and
  did not end on the verdict. The two 6/7 runs only missed the final `VERDICT` line. The grader
  passed their Non vérifié assertion on a closing French sentence listing what was not run, a
  borderline call: with a strict labelled-section reading they drop to 5/7.

## What the numbers mean

- **Discriminating assertions**: A2 (missed by all 9 baselines where asked), R1 (missed by 4 of
  6 baselines where asked), P1, and the format assertions (final `VERDICT` line, French section
  names). **Non-discriminating**: the traps (Switch 24 px target, 44 px threshold, boolean
  `invalid` prop, `useLayoutEffect`) and the legacy overlay's R1. Every run in both arms passed
  them, so the overlay and trap handling show no gain.
- **The baselines reported more real issues outside the planted list.** Graders verified 11 to
  13 extra real findings per baseline full review against 6 to 9 with the skill (French: 11 to
  12 against 8 to 10; a11y: 4 to 6 against 4 to 9). Examples: an empty package (no build,
  `noEmit`), IconButton's `aria-label` overwriting the caller's, missing `:disabled` styles, a
  test file that cannot run without a DOM environment. The skill trades breadth for the
  planted, harder defects and a stable report format.
- **No false finding with the skill.** No finding reported in any with-skill run was judged
  false. Each baseline full review carried one over-confident claim (A2 or R1 "in good shape",
  or bundle size "fine" without a build).
- **Cost.** The skill adds about 89% wall time and 23% tokens per review: it runs the script
  and verifies each finding. Some runs also rendered in a headless browser, a process claim the
  graders could not verify.
- **Bias that remains.** The skill's author also wrote the fixture and the assertions, so the
  planted defects match the skill's rule set. `src/legacy/REVIEW.md` names the switched-off rule
  by the skill's own id, and the root `REVIEW.md` states the 24 px floor for both arms. This
  measures whether the skill does what it claims, not how it compares on arbitrary code.
- **`grade.py` disagrees with the blind graders.** It fails one with-skill a11y run on "no
  finding on the Switch target size" because a Switch hover / forced-colors finding cites
  Switch lines near size words; the graders passed it (the finding is about hover and a
  `flex-shrink` layout bug, not target size). It also fails two baselines on the Not checked
  format where the graders accepted unlabelled prose. Known `grade.py` false positives, not
  fixed in this change.

## Triggering

Does the description make Claude load the skill on its own? Measured with `skill-creator`'s
trigger eval (`scripts/run_eval.py`) on a 20-query set written for this skill:

- 10 should-trigger: front-end reviews of the author's own repositories, PRs, branches and
  components, in French and English, on several stacks.
- 10 near-miss should-not-trigger: reviewing an employer's repository against its own
  conventions, backend Go reviews, writing a `REVIEW.md`, fixing a bug, writing a test, an
  architecture audit, a Terraform review, a simplification, a WCAG question.
- 3 runs per query, Claude Opus 5.5, the author's own Claude Code setup with its other review
  skills installed, user hooks disabled.
- `run_eval.py` does not run on Windows as shipped (it reads the subprocess pipe with
  `select.select`); it ran from a patched copy (a reader thread instead of `select`, hooks
  disabled). The patch is not part of this repository.

| Variant | Should trigger | Should not trigger | Query-level recall |
|---|---|---|---|
| As installed | 2/30 runs | 0/30 runs | 0/10 |
| Registered as a project skill, load counted at any point | 4/30 runs | 0/30 runs | 0/10 |

No query reached the 50% trigger rate, and there was no false positive. A diagnostic showed the
skill listed in every session; the model mostly started reviewing directly with Bash and Glob.

**The skill under-triggers badly**: in practice it must be invoked explicitly (`/front-review`
or by name).

`skill-creator`'s description optimizer (`scripts/run_loop.py`, same patched copy, Opus 5.5
proposing the rewrites) then ran 5 iterations on a 12-query train split, checked against the 8
held-out queries, 3 runs per query. No rewrite beat the original: every iteration scored 6/12 on
train and 4/8 on test, passing every should-not-trigger query and no should-trigger one. Rewrites
that led with the user's phrasings, the target repositories and the competing review skills
reached 3/30 should-trigger runs at most, noise at this sample size. The description is kept as
is: for every description tried, the model reviewed the code directly instead of loading a skill.

## Not done

- Human review of the outputs in the eval viewer: generated and handed to the author, no
  feedback yet.
- Runs on Linux or macOS.

## Runs not completed

None. All 18 benchmark answers were produced and graded, and all 60 trigger runs of each
variant completed.

## Reproducing

```bash
# from the repo root: the script half
bash skills/front-review/scripts/front-review.sh skills/front-review/evals/fixtures/sample-ui-lib
```

Graded answers go in a run directory as `full-review.md`, `a11y-pass.md` and `fr-pr-style.md`,
then `python3 skills/front-review/evals/grade.py <run-dir>`; exit code 0 means every assertion
passed. On Windows, set `PYTHONUTF8=1`. The blind grading and the aggregate come from
`skill-creator`'s benchmark flow over the same three evals.
