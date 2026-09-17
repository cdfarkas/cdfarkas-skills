# sentry-triage — evaluation results

Method: each prompt in `evals.json` is given to an agent **with** the skill and to an
agent **without** it, in isolated sessions. Both answers are graded by `grade.py` —
pure regex over the answer text, no model in the loop, so a rerun grades identically.

## Status: not yet run

The with/without benchmark has not been run. What has been verified, on 2026-09-17,
against a private Sentry project (30 unresolved issues, one React front-end):

- the script runs end to end in ~5 s and every error path in `reference.md` exits
  non-zero with the documented last line (no token, bad token, unknown project slug
  and id, unknown issue, issue outside the period);
- `grade.py` scores the script's own output 8/8, 4/4 and 3/3 once a two-entry ranked
  list is appended to the first case — so the assertions match what the skill is asked
  to produce and are not vacuous.

The recorded answers are not published because they carry internal file paths and
customer names from the issue titles. The harness is here so anyone can reproduce the
run against their own project.

## Scores

| Case | With the skill | Without |
|---|---|---|
| `url-triage` | not measured | not measured |
| `slack-format` | not measured | not measured |
| `unknown-project` | not measured | not measured |
