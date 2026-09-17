# cdfarkas-skills

Agent skills that ship with the evidence they work: every skill carries the prompts
it was tested on, the assertions it was graded against, and its scores with and
without the skill.

## Skills

| Skill | What it does | Needs |
|---|---|---|
| [`pr-todo`](skills/pr-todo/) | Every open pull request you have to act on in a GitHub organization, as one raw table with links, status and blockers | `gh`, `jq` |
| [`sentry-triage`](skills/sentry-triage/) | The unresolved issues of a Sentry project ranked by impact, then what to fix first by severity and complexity | Sentry token, `curl`, `jq` |

Each folder has its own README with usage, output and evaluation results.

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

## How these are built

Behaviour goes in a script, not in prose an agent has to interpret; then the skill is
evaluated with and without itself, and the evaluation is published, failed runs
included. See [`docs/how-these-skills-are-built.md`](docs/how-these-skills-are-built.md).

## License

Apache 2.0.
