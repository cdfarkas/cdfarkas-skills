# How these skills are built

Four rules, each of which came from something going wrong.

## 1. Behaviour goes in a script, not in prose

A skill can tell an agent what to do in markdown, and the agent will improvise the
rest. That improvisation is where skills diverge between models and between runs.

`pr-todo` puts every decision in bash and jq: which GitHub queries to run, how to
batch them, what counts as a blocker, how to render a row. `SKILL.md` says when to
run it and to relay its output unchanged. The result behaves identically under any
agent with a shell, and a bug in it is a bug you can reproduce without an agent at
all.

The test for whether a rule belongs in the script: could two reasonable agents
read this sentence and produce different output? If yes, it is not a sentence, it
is code.

## 2. Evaluate before publishing, and publish the evaluation

The method, per skill:

1. Write 3 prompts a real person would actually type, in the words they would use.
2. Run each one twice — an agent **with** the skill, an agent **without** — in
   isolated sessions.
3. Grade both with a script, not by reading. Assertions are regex over the answer
   text, so a rerun grades identically and a disagreement is a bug in the
   assertion rather than noise.
4. Fix what the run exposes. Rerun.
5. Commit the prompts, the assertions, the grader and the scores.

The baseline matters more than the score. A skill that scores 7/7 where an agent
without it also scores 7/7 is decoration. What justifies a skill is the gap.

For `pr-todo`, the run found three defects that no amount of code review would
have surfaced, because all three were about what the output *said*, not what the
code did. The worst: a GitHub login that does not exist produced `nothing to do` —
a typo in a flag reading as good news. They are listed in
[`../skills/pr-todo/evals/RESULTS.md`](../skills/pr-todo/evals/RESULTS.md).

## 3. Report what happened, including the run that failed

One baseline in the `pr-todo` evaluation aborted on an API rate limit before
producing an answer. The grader scored the missing file 0/7, which would have
looked like a crushing win for the skill.

It is reported as **not measured**. A published evaluation is only worth
something if the inconvenient runs are in it, and the temptation to keep a
flattering artefact is exactly why the rule has to be written down.

## 4. A skill that changes state ships `--dry-run`

The first three skills only read. `pr-guardian` is the first one that writes: it
rebases, amends, force-pushes and edits pull requests, from a background agent the
person is not watching. An agent that pushes must be inspectable before it acts.

So every script under `skills/*/scripts/` that can push, open, edit, merge or close
a pull request, or call a write endpoint of the API, takes `--dry-run`: it prints
every action it would take, one `dry-run: would …` line each, and executes none.
Read-only skills (`pr-todo`, `sentry-triage`) do not carry the flag.

`scripts/validate-skills.py` enforces it with a coarse grep, on purpose: a false
positive is fixed by adding the flag, a false negative would be a push nobody could
preview.

## On the tooling

Anthropic ships the evaluation machinery first-party in the `skill-creator` skill
(`run_eval.py`, `run_loop.py`, `aggregate_benchmark.py`), including with-skill
versus without-skill benchmarks. It is worth using directly. One caveat found the
hard way: its description-optimization loop produces very long descriptions for
gains inside the noise. Treat it as a diagnostic for a skill that fails to
trigger, not as a source of descriptions.
