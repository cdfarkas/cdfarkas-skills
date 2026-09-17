# cdfarkas-skills

Agent skills that ship with their own with/without benchmark.

[![ci](https://github.com/cdfarkas/cdfarkas-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/cdfarkas/cdfarkas-skills/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue?style=flat)](LICENSE)
[![Agent Skills standard](https://img.shields.io/badge/Agent%20Skills-standard-green?style=flat)](https://agentskills.io/)
[![Runs on macOS, Linux and Windows](https://img.shields.io/badge/runs%20on-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey?style=flat)](.github/workflows/ci.yml)

## Why

Most published skills are prose an agent interprets, and two agents reading the same
sentence produce different output. Here the behaviour is a script; `SKILL.md` only says
when to run it and how to relay its output. Each skill is then run against an agent that
does not have it, on the same prompts, graded by regex rather than by a model. The
evaluation is published as it happened, including the runs that failed or did not complete.

## Skills

| Skill | What it does | Needs |
|---|---|---|
| [`pr-todo`](skills/pr-todo/) | Every open pull request you have to act on in a GitHub organization, as one raw table with links, status and blockers | `gh`, `jq` |
| [`sentry-triage`](skills/sentry-triage/) | The unresolved issues of a Sentry project ranked by impact, then what to fix first by severity and complexity | Sentry token, `curl`, `jq` |

Each folder has its own README with usage, output and evaluation results.

## Scores at a glance

| Skill | With the skill | Without | Time and tokens, mean | Details |
|---|---|---|---|---|
| `pr-todo` | 7/7, 6/6, 3/3 | not measured, 2/6, 0/3 | not measured | [RESULTS.md](skills/pr-todo/evals/RESULTS.md) |
| `sentry-triage` | 8/8, 4/4, 3/3 | 2/8, 2/4, 1/3 | 129 s and 85k with, 334 s and 117k without | [RESULTS.md](skills/sentry-triage/evals/RESULTS.md) |

Three prompts per skill, each run once with the skill and once without, in isolated
sessions. `not measured` means the baseline run aborted (an API rate limit, in the
`pr-todo` case) before producing an answer; it is reported as such, never as a zero.

## What the output looks like

`pr-todo`, as the agent relays it, unchanged:

```
PR to-do · @you · your-org · 2026-09-10 · 12

| PR | Role | Status | Blockers | Age | Title |
|---|---|---|---|---|---|
| [api#1420](https://github.com/your-org/api/pull/1420) | assignee | conflict | conflicts | 6d | fix(auth): refresh the token before… |
| [web#88](https://github.com/your-org/web/pull/88) | reviewer | ci-failing | ci: build, lint; 2 unresolved threads | 2d | feat(search): rank by recency |
| [infra#12](https://github.com/your-org/infra/pull/12) | author | blocked | needs approval | 1d | chore(ci): pin the runner image |
```

## Install

```
/plugin marketplace add cdfarkas/cdfarkas-skills
/plugin install pr-todo@cdfarkas-skills
/plugin install sentry-triage@cdfarkas-skills
```

Or copy a skill folder into `~/.claude/skills/` (or your agent's equivalent).
[Agent Skills](https://agentskills.io/) is an open standard implemented by Claude
Code, Codex, Cursor, Gemini CLI, Copilot and others; only the install command above
is Claude Code specific.

## How a skill gets in

1. **Script over prose.** If two agents could read a sentence and produce different
   output, it is code, not a sentence. The script carries the behaviour; `SKILL.md`
   says when to run it.
2. **Evaluated with versus without.** Every prompt in `evals/evals.json` runs twice, one
   agent with the skill and one without, graded by the skill's own `evals/grade.py`. A
   skill that scores the same as the baseline does not ship.
3. **Results published, failures included.** `evals/RESULTS.md` carries the method, the
   run date, the scores table, what the baselines got wrong, and every run that did not
   complete, reported as not measured.
4. **CI on Linux and Windows Git Bash.** Scripts are bash 3.2 compatible, parse under
   both, and the repo is grepped for personal paths on every push.

The reasoning behind the rules, and what each one caught:
[`docs/how-these-skills-are-built.md`](docs/how-these-skills-are-built.md).

## Next

`pr-guardian`: a background agent that keeps a pushed branch mergeable (rebase, CI
fixes, review triage), with a `--dry-run` mode and a prerequisite doctor. In progress.

## Author

[Clément Farkas](https://github.com/cdfarkas), front-end tech lead.

## License

Apache 2.0. See [LICENSE](LICENSE).
