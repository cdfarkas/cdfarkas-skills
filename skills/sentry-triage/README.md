# sentry-triage

The unresolved issues of a Sentry project ranked by impact, then what to fix first.
The script computes the severity, the trend, the innermost in-app frame, the failure
origin and the clusters sharing one root cause; the agent adds the complexity call
and the priority order.

```
Sentry triage · your-org/web · prod · 14d · is:unresolved · 30 issues

| Issue | Sev | Score | Users | Events | Trend | Status | Origin | Where | Title |
|---|---|---|---|---|---|---|---|---|---|
| [WEB-C](https://your-org.sentry.io/issues/76441190/) | critical | 410 | 24 | 33 | → | ongoing | browser | - | Error: [object HTMLLinkElement] |
| [WEB-2G](https://your-org.sentry.io/issues/77240272/) | high | 239 | 11 | 49 | ↑ | escalating | app | config/routing/routes.tsx:66 useRoutes | Error: useAuthContext must be used within a Provider |
| [WEB-17](https://your-org.sentry.io/issues/76670525/) | high | 237 | 21 | 27 | → | ongoing | network | dist/client/proxy-client.js:213 w | ApiClientError: API Error: 401 |

Clusters (one root cause, fix once):
- network / API Error: 401 — 6 issues · 79 users · 101 events · score 928 · WEB-17, WEB-18, WEB-P, …
```

## Usage

```
bash scripts/sentry-triage.sh "https://your-org.sentry.io/issues/?environment=prod&project=123&statsPeriod=14d"
bash scripts/sentry-triage.sh --org your-org --project web --env prod [--period 30d] [--format slack]
bash scripts/sentry-triage.sh --org your-org --project web --issue WEB-2G [--tags release,browser,url]
bash scripts/sentry-triage.sh --doctor
```

Paste a Sentry issue-stream URL and everything is read from it. `--issue` details one
issue (frames innermost first, tag breakdown, daily counts); `--doctor` checks tools,
token, scopes and access before the first run. Auth is `SENTRY_AUTH_TOKEN` or
`~/.sentryclirc`; `SENTRY_ORG` / `SENTRY_PROJECT` / `SENTRY_ENVIRONMENT` save the
flags. Runs on macOS, Linux and Windows under Git Bash. Score formula, origin rules,
columns and every failure line: [`reference.md`](reference.md).

Project-agnostic: a `## Sentry` section in the host project's `CLAUDE.md` declares
the org and project, how paths map to the working tree, the known noise and the
owners — see [`SKILL.md`](SKILL.md).

## Evaluation

Scores: 8/8, 4/4 and 3/3 on its assertions with the skill; 2/8, 2/4 and 1/3 without,
in a third of the time. Full numbers, method and what the baselines got wrong in
[`evals/RESULTS.md`](evals/RESULTS.md).
