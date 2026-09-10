# pr-todo — evaluation results

Method: each prompt in `evals.json` was given to an agent **with** the skill and to
an agent **without** it, in isolated sessions. Both answers were graded by
`grade.py` — pure regex over the answer text, no model in the loop, so a rerun
grades identically.

Run on 2026-09-09 against a private organization; the recorded answers are not
published because they carry internal repository names and colleague logins.
The harness is here so anyone can reproduce the run against their own
organization.

## Scores

| Case | With the skill | Without |
|---|---|---|
| `own-prs-md` | 7/7 | not measured |
| `other-dev-slack` | 6/6 | 2/6 |
| `unknown-user` | 3/3 | 0/3 |

The `own-prs-md` baseline is reported as **not measured**, not as a zero: that run
aborted on an API rate limit before producing an answer. Scoring a missing file as
a failure would flatter the skill.

## What the baselines got wrong

Without the skill, agents given the same prompts each invented their own column
set, mixed prose into the table, and produced links in formats that do not render
where they were asked to be pasted. One spent roughly five minutes on 44 pull
requests; the script takes about twenty seconds on 100, because the agents queried
GitHub one PR at a time.

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
