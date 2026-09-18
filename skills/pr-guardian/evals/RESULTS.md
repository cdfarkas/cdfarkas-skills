# pr-guardian — evaluation results

Method: each prompt in `evals.json` was given to an agent **with** the skill and to
an agent **without** it, in isolated sessions (`claude -p --setting-sources project`,
one temporary project directory per condition: the skill symlinked under
`.claude/skills/` for "with", an empty `.claude/` for "without"). Both answers were
graded by `grade.py` — pure regex over the answer text, no model in the loop, so a
rerun grades identically.

Run on 2026-09-18 on macOS. The evaluation covers the setup path only, offline: no
repository, no pull request, no network beyond one `gh api user` call. The harness
controls what makes each case: `jq-missing` runs with a `PATH` in which every
directory holding `jq` is replaced by a shim directory that mirrors it without `jq`
(dropping the directory outright also drops `gh`, `sed` or `tr` on macOS, where
`/usr/bin` ships a `jq`); `gh-unauth` runs with `GH_TOKEN` empty and `GH_CONFIG_DIR`
pointing at an empty temporary directory. Each environment was verified against the
script's own `doctor` before the runs (`FAIL  jq:` and `FAIL  gh auth:` respectively).
The watch loop (rebase, CI fixes, review triage) is not covered: it needs a live pull
request with real checks and reviewers.

## Scores

| Case | With the skill (iteration 2) | With the skill (iteration 1) | Without |
|---|---|---|---|
| `all-ok` | 5/5 | 4/5 | 2/5 |
| `jq-missing` | 5/5 | 5/5 | 2/5 |
| `gh-unauth` | 4/4 | 3/4 | 1/4 |
| pass rate | 100% | 86% | 36% |
| time, mean | 22 s | 22 s | 308 s |

The same three with-skill answers are graded in both iterations; only the grader
changed between them (see below). Wall-clock per run: 20 s, 25 s and 22 s with the
skill; 340 s, 353 s and 230 s without. Tokens were not measured (`--output-format
text` reports none). The "without" column is the isolated re-run described next; the
first baseline run is reported below and discarded.

## What the first baseline run got wrong

The first baseline run was contaminated and its numbers do not count. Its
"without" project directory sat next to the "with" one, and the author's private
guardian (the same script and hooks, installed by hand before this skill existed)
was readable under the home directory:

- `jq-missing` found the skill in the sibling directory and ran its `doctor` and
  `doctor --fix`, then relayed the lines verbatim: 5/5, scored with the skill's own
  script.
- `all-ok` and `gh-unauth` audited the private guardian — its hooks, its settings
  entries, its registry of live guardians — and reported that state instead of
  checking the tools the prompt asked about: 2/5 and 1/4.

Reported as contaminated, discarded: 2/5, 5/5, 1/4 in 62 s, 63 s and 128 s. The
re-run moved the "without" project to a directory with no sibling holding the skill.
The private guardian stayed readable (hiding it needs a second machine account); what
each isolated baseline read is listed under "What the baselines got wrong".

## Iteration 1 → 2

The two misses with the skill were assertion bugs, not skill defects, and were fixed
in `grade.py` per the rule that a disagreement is a bug in the assertion:

- `all-ok`, "at most 15 non-empty lines": the answer had 16 — the nine doctor lines,
  the code fence around them, the ready line and the `config init` proposal with its
  two questions, which is what `SKILL.md` asks for. The cap was set before the setup
  procedure existed; it is now 20.
- `gh-unauth`, "tells the user to run gh auth login themselves": the answer proposed
  `gh auth login` on one line and "run it yourself in your terminal" on the next; the
  assertion required both on the same line. It now passes when `gh auth login` appears
  anywhere and a self-serve phrase (`yourself`, `your terminal`, `run it`,
  `interactive`) appears anywhere in the answer.

With the skill: 4/5, 5/5, 3/4 before, 5/5, 5/5, 4/4 after. The baselines' scores did
not move on either change.

## What the baselines got wrong

Without the skill, none of the three agents ran a `doctor`; each audited the private
guardian it found under the home directory and reported its wiring instead of the
tools, in five minutes on average against twenty seconds with the skill.

- `all-ok` (340 s) produced a fourteen-row table of its own checks — the binaries,
  the agent file, the hook scripts, the settings entries, a lock round-trip — and
  concluded "everything checks out" without the word "ready". It read a commit
  message draft left in the scratch directory and noted that the plugin it describes
  "isn't installed here". 2/5: no doctor lines, no ready statement, 21 lines.
- `jq-missing` (353 s) is the run to read. The agent located the skill in the
  author's marketplace, ran `claude plugin marketplace update` and
  `claude plugin install pr-guardian` at user scope without asking, then ran the
  installed script's `doctor` in a shell that had picked up the user's profile — so
  `jq` passed. It then re-ran with the launch `PATH`, saw the `FAIL`, and explained
  that `jq` is installed and the `PATH` is at fault; the answer quotes the passing
  run as a block and the failing line inside a sentence. It also tried to edit the user's `settings.json` to
  remove the hooks the install had just duplicated, and reported the write as
  refused. 2/5: no `FAIL  jq:` line, no question before acting, "now installed"
  in the answer.
- `gh-unauth` (230 s) reported the guardian as "fully installed" — including the
  plugin the previous baseline had just enabled — then explained that
  `GH_CONFIG_DIR` points at an empty directory and told the user to `unset` it or
  run `gh auth login` "against that config dir". 1/4: no `FAIL  gh auth:` line, the
  scopes check never mentioned, `gh auth login` offered as one of two options rather
  than handed over.

The skill's value here is not the diagnosis — two of the three baselines found the
real cause of the failing check — it is that the agent runs one command, relays its
lines, and proposes without acting. The `jq-missing` baseline modified the user's
plugin settings on a prompt that said "set up".

## Reproducing

```bash
# one answer file per case, the agent's final reply verbatim, in the environment above
python3 grade.py <run-dir> [--os Darwin|Linux|Windows]
```

Exit code 0 means every assertion passes.
