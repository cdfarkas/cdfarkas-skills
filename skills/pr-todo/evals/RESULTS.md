# pr-todo — evaluation results

Method: each prompt in `evals.json` was given to an agent **with** the skill and to
an agent **without** it, in isolated sessions. Both answers were graded by
`grade.py` — pure regex over the answer text, no model in the loop, so a rerun
grades identically.

Run on 2026-09-09 and re-run on 2026-09-17 against the same private organization;
the recorded answers are not published because they carry internal repository
names and colleague logins. The harness is here so anyone can reproduce the run
against their own organization.

The re-run exists because the `passed` counter in `grade.py` counted every
assertion instead of the passed ones (fixed in this commit, `sum(... if ok)`), so
the `7/7, 6/6, 3/3` printed on 2026-09-09 could not be told apart from partial
passes. The FAIL lines and the exit code were always correct; the re-run with the
fixed counter confirms the scores. Two attempts on `other-dev-slack` did not
count: the first target developer had no open pull requests (`nothing to do`),
which makes the link and blocker assertions unsatisfiable by construction, so the
case was re-run on a developer with open PRs; the next attempt hit a GitHub HTTP
502 on the mergeability batch and the skill relayed the error line instead of a
partial table — a harness incident, not a score. The third attempt is the one
graded.

## Scores

| Case | With the skill | Without |
|---|---|---|
| `own-prs-md` | 7/7 | 2/7 |
| `other-dev-slack` | 6/6 | 2/6 |
| `unknown-user` | 3/3 | 0/3 |

"With the skill" is the 2026-09-17 re-run graded by the fixed counter: 85, 119
and 0 pull requests, 82 s, 35 s and 12 s of agent wall-clock (the script itself
takes about 35 s on 85 PRs). The `own-prs-md` baseline was measured on
2026-09-17 and took 7 min 25 s over 38 GitHub calls, five of which were GraphQL
batches that returned 502 and were retried; the 2026-09-09 baseline had aborted
on an API rate limit and was reported as **not measured** until this re-run. The
other two baselines are the 2026-09-09 runs.

## What the baselines got wrong

Without the skill, agents given the same prompts each invented their own column
set, mixed prose into the table, and produced links in formats that do not render
where they were asked to be pasted. One spent roughly five minutes on 44 pull
requests; the script takes about twenty seconds on 100, because the agents queried
GitHub one PR at a time.

The `own-prs-md` baseline passed two assertions: every one of its 31 rows carried
a clickable link, and at least one row named a blocking reason. It failed the
rest: a prose sentence with a timestamp instead of the `PR to-do · @user · org ·
date · count` header, its own column set (`PR | What | State | Why it is stuck |
Age`), four `##` sections of commentary around the table, no role vocabulary for
the developer's own PRs, and a status column outside the fixed vocabulary. It
also spent its first three searches on a login it had been told was the user's
and that does not exist, then recovered by reading `gh api user`; the skill's
script probes the login up front.

The `unknown-user` baseline is the interesting failure. Asked about a login that
does not exist, an agent without the skill reported an empty list with an
explanation — which reads as "you have nothing to do". That is the exact failure
the skill was changed to prevent.

## Defects the evaluation found in the skill itself

The first version of the skill scored worse than it does now. Three defects came
out of the run and were fixed:

1. **A login that does not exist returned `nothing to do`**, indistinguishable
   from a developer with no open pull requests. A typo in `--user` read as good
   news. The script now probes the login and exits with an error.
2. **A draft PR was labelled `needs approval`** on top of a `draft` status that
   already said it. `needs approval` is now reserved for non-draft PRs.
3. **A change request the reported developer made themselves** was listed as
   `changes requested: <their own login>` in their own to-do. It now reads `you`.

None of the three would have been caught by reading the code. All three came from
looking at what the skill actually produced.

## Reproducing

```bash
# produce one answer file per case, however your agent runs them
python3 grade.py <run-dir> --org <org> --user <you> --other <colleague> --unknown <bogus-login>
```

Exit code 0 means every assertion passed.
