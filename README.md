# ai-skills

Agent skills that ship with the evidence they work.

Every skill here carries an `evals/` directory: the prompts it was tested on, the
assertions it was graded against, and the scores with and without it. That is the
part almost nobody publishes, and it is the reason to trust any of this.

## Install

```
/plugin marketplace add cdfarkas/ai-skills
/plugin install pr-todo@cdfarkas-skills
/plugin install sentry-triage@cdfarkas-skills
```

Or copy the skill folder into `~/.claude/skills/` (or your agent's equivalent).

## Skills

### `pr-todo`

Every open pull request you have to act on in a GitHub organization — review
requested, authored, or assigned — as one raw table. Clickable links, merge
status, the concrete reason each PR is stuck, and age.

```
PR to-do · @you · your-org · 2026-09-10 · 12

| PR | Role | Status | Blockers | Age | Title |
|---|---|---|---|---|---|
| [api#1420](https://github.com/your-org/api/pull/1420) | assignee | conflict | conflicts | 6d | fix(auth): refresh the token before… |
| [web#88](https://github.com/your-org/web/pull/88) | reviewer | ci-failing | ci: build, lint; 2 unresolved threads | 2d | feat(search): rank by recency |
| [infra#12](https://github.com/your-org/infra/pull/12) | author | blocked | needs approval | 1d | chore(ci): pin the runner image |
```

`--format slack` gives the same thing as mrkdwn bullets, ready to paste.
`--user <login>` reports on someone else. It needs `gh` and `jq`.

Scores: 7/7, 6/6 and 3/3 on its assertions with the skill; 2/6 and 0/3 on the two
baselines that completed without it. Full numbers and method in
[`skills/pr-todo/evals/RESULTS.md`](skills/pr-todo/evals/RESULTS.md).

### `sentry-triage`

The unresolved issues of a Sentry project ranked by impact, then what to fix first.
The script computes the severity (users × 10 + events, weighted by level, unhandled
and escalating / regressed), the trend, the innermost in-app frame, the failure origin
and the clusters sharing one root cause; the agent adds the complexity call and the
priority order, reading the code when the project's `CLAUDE.md` says where it lives.

```
Sentry triage · your-org/web · prod · 14d · is:unresolved · 30 issues

| Issue | Sev | Score | Users | Events | Trend | Status | Origin | Where | Title |
|---|---|---|---|---|---|---|---|---|---|
| [WEB-2G](https://your-org.sentry.io/issues/77240272/) | high | 239 | 11 | 49 | ↑ | escalating | app | config/routing/routes.tsx:66 useRoutes | Error: useAuthContext must be used within a Provider |
| [WEB-17](https://your-org.sentry.io/issues/76670525/) | high | 237 | 21 | 27 | → | ongoing | network | dist/client/proxy-client.js:213 w | ApiClientError: API Error: 401 |
| [WEB-C](https://your-org.sentry.io/issues/76441190/) | critical | 410 | 24 | 33 | → | ongoing | browser | - | Error: [object HTMLLinkElement] |

Clusters (one root cause, fix once):
- network / API Error: 401 — 6 issues · 79 users · 101 events · score 928 · WEB-17, WEB-18, WEB-P, …
```

Paste a Sentry issue-stream URL and everything is read from it; `--issue WEB-2G`
details one issue (frames innermost first, release / browser / url breakdown);
`--format slack` for a channel; `--doctor` checks tools, token, scopes and access
before the first run. Project-agnostic and platform-agnostic (macOS, Linux, Windows
under Git Bash): a `CLAUDE.md` `## Sentry` section
declares the org, the path mapping, the known noise and the owners. Needs a Sentry
API token, `curl` and `jq`.

Evaluation harness in [`skills/sentry-triage/evals/`](skills/sentry-triage/evals/);
the with/without benchmark is not run yet and
[`RESULTS.md`](skills/sentry-triage/evals/RESULTS.md) says so.

## Not Claude-only

[Agent Skills](https://agentskills.io/) is an open standard, authored by Anthropic
and implemented by ChatGPT and Codex, Cursor, Gemini CLI, GitHub Copilot, VS Code,
Goose and a long list of others — agentskills.io keeps the current one. A skill
folder here works in any of them.

The install command above and the `commands/` entry points are Claude Code
specific; the skills themselves are not.

## How these are built

Behaviour goes in scripts, not in prose an agent has to interpret. A script
behaves identically under every agent that can run a shell; a prose-heavy skill
degrades differently on each model. `SKILL.md` says when to run the thing and how
to read its output, and nothing more.

Then it gets evaluated, and the evaluation is published. See
[`docs/how-these-skills-are-built.md`](docs/how-these-skills-are-built.md).

## License

Apache 2.0.
