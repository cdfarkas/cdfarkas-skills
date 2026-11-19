# fr-dpia — evaluation results

Method: each prompt in `evals.json` was given to an agent **with** the skill and to an
agent **without** it, in isolated sessions (headless `claude -p`, Claude Code 2.1.328,
2026-11-19). Each case ran in a fresh git repo with no project to read; the skill was
copied to `.claude/skills/` only in the "with" arm. Both arms loaded the author's
user-level Claude Code configuration, so the baseline is not a bare model. One run per
case: variance was not measured, so a single-assertion gap is not a stable difference.
Answers are graded by `grade.py`, pure regex over the answer text (plus the saved draft
for the draft-content assertions), no model in the loop, so a rerun grades identically.
The recorded answers are not published.

## Scores

Run 2, after the fix to the output contract and the grader (the headline):

| Case | With the skill | Without |
|---|---|---|
| `fr-children-reports` | 7/7 | 5/7 |
| `en-hr-analytics` | 8/8 | 1/8 |
| `en-newsletter-no-dpia` | 4/5 | 3/5 |
| Total | 19/20 | 9/20 |

Run 1, kept as history (before the fix), with the scores printed at the time and the
scores of the current grader on the same files:

| Case | With (then, now) | Without (then, now) |
|---|---|---|
| `fr-children-reports` | 7/7, 7/7 | 2/7, 3/7 |
| `en-hr-analytics` | 2/8, 2/8 | 1/8, 1/8 |
| `en-newsletter-no-dpia` | 5/5, 5/5 | 2/5, 3/5 |

Regrading run 1 with the current grader moves two baseline cases up by one assertion
(5/20 to 7/20 without) and leaves the with arm unchanged (14/20). Run 2 regraded with the
current grader gives exactly the scores above, no difference. In run 1 the with-arm HR
case saved its draft in a system temp directory outside the project and only summarised
it, which is why it scored 2/8; that is the defect the fix addresses.

## The failure with the skill

`en-newsletter-no-dpia`, assertion "the verdict is that a DPIA is not indicated or not
required": **failed**. The skill answered "DPIA undetermined", because three criteria
were unknown (systematic monitoring through open and click tracking, large scale,
vulnerable subjects such as minors) and two of them being met would flip the verdict.
The assertion was not changed after seeing the result. This is the skill being stricter
than the case expected, not a malfunction: it declined to call "not indicated" on facts
nobody supplied, and asked the three questions. The owner decides whether the case should
accept "undetermined, probably not" for a form that stores an email and a date, or whether
the skill should lean towards "not indicated" when the unknowns are that thin. The without
arm said "Probably not" on the same facts and added the tracking-pixel caveat itself.

## What the baselines got wrong, and what they did well

Without the skill, from the run-2 answers and drafts:

- **No count out of nine.** All three answers listed or discussed the criteria but none
  gave an N/9 tally, so none of them showed which criteria were established and which were
  assumed.
- **No hand-off line to the DPO** in the two English cases (the French one has a closing
  line that sends the result to a DPO or lawyer and passed).
- **No TODO questions.** The French baseline concluded "Probablement oui" on the
  children's reports without asking what the reports contain; it assumed health data
  ("presque toujours") and cited the CNIL list "de mémoire", flagging that it had not
  checked it. The with arm kept 8 of 9 criteria unknown and named the two answers that
  would decide.
- **The HR baseline wrote a full draft anyway** (`DPIA-hr-analytics.md` at the repo root,
  about 17 KB, 10 risks, a 12-item action plan, a CSE and AI Act section, a devil's-advocate
  section). It did not use the CNIL severity labels (it used English "negligible to maximum"
  on a 1-4 scale), assessed illegitimate access but not the three feared events as such,
  used no TODO markers (it invented "ASSUMPTION" statements and `[brackets]` instead, so
  facts were guessed rather than left open), and stated the art. 36 outcome as a
  conclusion ("expected residual level is Medium") instead of putting it to the DPO.
- **Done well.** Every baseline reached a defensible verdict, flagged that it worked from
  the prompt only, and added useful practical points the skill does not cover: the HDS
  hosting warning and the recital 91 exemption for a lone practitioner (French case),
  consent, retention, processor and transfer duties (newsletter), works-council
  consultation and the AI Act (HR). The HR draft is longer and arguably richer than the
  skill's, but it rests on assumed facts.

The pattern is the one the skill is built for: the baselines are competent but conclude on
facts they do not have, and do not produce the count, the TODO list or the DPO hand-off.

## Caveats

- The output contract and the grader changed between the runs: the skill now keeps the
  draft and its answers file under `docs/dpia/` and relays the script's summary verbatim,
  and `grade.py` reads a leading verdict word and grades the saved draft. The two runs are
  therefore not the same experiment, and run 2 is the one that tests the current skill.
- The harness changed too: it now also copies a baseline draft saved elsewhere in the case
  repo (the HR baseline wrote to the repo root, outside `docs/dpia/`), so the baseline
  draft is graded rather than ignored.
- One run per case, both arms under the author's own configuration; one assertion is one
  point of noise.

## Reproducing

```bash
# produce one answer file per case, however your agent runs them,
# plus <case>.draft.md when the agent saved a draft (see the notes in evals.json)
python3 grade.py <run-dir>
```

Exit code 0 means every assertion passed.
