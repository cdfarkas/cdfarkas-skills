# cdfarkas-skills — working rules

Public repository. Every skill ships with the evidence it works; nothing personal or
company-specific goes in (CI greps for `/Users/…` and `/home/…`).

## Before a skill is committed

1. **Behaviour in a script, not in prose.** If two agents could read a sentence and
   produce different output, it is code, not a sentence. `SKILL.md` says when to run
   the script and how to read its output. See `docs/how-these-skills-are-built.md`.
2. **Evaluate with `skill-creator`, with-skill versus without-skill.** Use the
   `skill-creator` skill (Anthropic's first-party plugin) to run every prompt in
   `skills/<name>/evals/evals.json` twice — one subagent with the skill, one without —
   in isolated sessions, and grade both with the skill's own `evals/grade.py`.
   Prompts must be what a real person would type. A skill that scores the same as the
   baseline is decoration and does not ship.
3. **Publish the evaluation in `evals/RESULTS.md`**, in the shape of
   `skills/pr-todo/evals/RESULTS.md`: method, the run date, a scores table
   (with the skill / without), what the baselines got wrong, and every run that did
   not complete reported as **not measured** — never as a zero. If the run is not
   done yet, `RESULTS.md` says so; an absent or flattering results file is a defect.
4. **Run the CI locally** (`python3 scripts/validate-skills.py`,
   `python3 scripts/validate-evals.py`, `bash -n` on every `.sh`, the personal-path
   grep) before committing; the `windows` job in `.github/workflows/ci.yml` needs a PR
   to run, so open one. Any PR touching `skills/`, `scripts/` or the marketplace
   manifest bumps `metadata.version` in `.claude-plugin/marketplace.json` (semver; CI
   refuses the PR otherwise).

## Layout of a skill

```
skills/<name>/
  SKILL.md          frontmatter (name = directory, description ≤ 1024 chars) + body < 500 lines
  README.md         usage, sample output, evaluation — for humans
  reference.md      columns, vocabularies, failure lines — what SKILL.md points to
  scripts/          the implementation; bash 3.2 compatible, LF endings, runs under Git Bash
  evals/evals.json  prompts + assertions
  evals/grade.py    regex grader, no model in the loop
  evals/RESULTS.md  the published run
```

Register the skill in `.claude-plugin/marketplace.json`, give it a `README.md` in its folder (usage, sample output, evaluation) and one row in the root `README.md` table.
