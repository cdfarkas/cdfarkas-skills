# sentry-triage — evaluation results

Method: each prompt in `evals.json` was given to an agent **with** the skill and to
an agent **without** it, in isolated subagent sessions (Claude Code, `skill-creator`
harness). Both answers were graded by `grade.py` — pure regex over the answer text,
no model in the loop, so a rerun grades identically.

Run on 2026-09-17 against a private Sentry project (one React front-end, 30–33
unresolved issues in production over 14 days). The recorded answers are not published
because they carry internal file paths and customer names from the issue titles. The
harness is here so anyone can reproduce the run against their own project.

## Scores

| Case | With the skill (iteration 2) | With the skill (iteration 1) | Without |
|---|---|---|---|
| `url-triage` | 8/8 | 7/8 | 2/8 |
| `slack-format` | 4/4 | 3/4 | 2/4 |
| `unknown-project` | 3/3 | 2/3 | 1/3 |
| pass rate | 100% | 77% | 36% |
| time, mean | 129 s | 221 s | 334 s |
| tokens, mean | 85k | 99k | 117k |

The baselines ran once, in iteration 1, and are reused in iteration 2: "without the
skill" did not change between the two.

## What iteration 1 found

The three misses with the skill were one defect — prose leaking around the raw output:

- `url-triage`: one ranked entry read `complexity none, dying`, outside the S / M / L /
  noise vocabulary the reader is told to expect.
- `slack-format`: a sentence in front of the bold header, which the user would have
  had to delete before pasting.
- `unknown-project`: thirteen lines of rerun advice and `--doctor` suggestions instead
  of the one error line, on a prompt that said "raw output only".

`SKILL.md` was rewritten on those three points — the answer starts at the script's
header, the complexity vocabulary is closed, the failure line is the whole answer —
and iteration 2 passes every assertion. Nothing in the script changed between the
two iterations.

## What the baselines got wrong

Without the skill, the agents each invented their own report: no table or a table
with their own columns, no cluster view, `[text](url)` links in a message meant for
Slack, and for the project that does not exist, a 16-line answer that listed the
organisation's 111 project slugs so the user could pick one. Two of the three were
also slower and heavier than the skill (the triage baseline took 546 s and 166k
tokens against 182 s and 93k with the skill), because each re-derived the API calls,
the pagination and the per-issue event reads from scratch.

The baselines' *analysis* was not bad — one of them found a real finding the skill's
run did not surface (a single production user served from a moving-channel remote).
What the skill buys is not insight, it is the same ranking every time, in a shape the
reader can paste, in a third of the time.

## Non-discriminating assertions

`unknown-project` / "the answer says the project is unknown" checks the script's
exact error line, so a baseline that says "does not exist" fails it by wording. That
is intended — the skill's contract is the verbatim line — but it means the assertion
measures conformance, not whether the agent noticed the project was missing (all
six runs did).
