---
name: sentry-triage
description: >
  Rank the unresolved Sentry issues of a project by impact and decide what to fix first:
  a deterministic severity score, the trend, the innermost in-app frame, the failure
  origin (app / vendor / network / browser), the clusters sharing one root cause, then
  a complexity call per issue. Use when someone asks which Sentry errors to fix first,
  what is hurting users in production, to triage or prioritize the error backlog, or
  pastes a Sentry issue-stream URL. Needs a Sentry API token, curl and jq.
license: Apache-2.0
---

# Sentry triage

Two steps. The script ranks by **severity** — it is deterministic, do not re-derive it.
You add **complexity**, which needs reading frames and, when the project tells you where
its code lives, the code itself.

## Step 1 — run the script

```bash
bash <skill-dir>/scripts/sentry-triage.sh [<sentry issues url>] [--org o --project p --env e --period 14d --query 'is:unresolved'] [--format md|slack]
bash <skill-dir>/scripts/sentry-triage.sh --issue <SHORT-ID> [--tags release,browser,url]
bash <skill-dir>/scripts/sentry-triage.sh --doctor [<url> | --org o --project p --env e]
```

`<skill-dir>` is the directory holding this file. Map what the caller said to flags:

| Caller says | Flag |
|---|---|
| pastes a Sentry URL (`https://<org>.sentry.io/issues/?...`) | pass it as the first argument, verbatim; org, project, environment, query and period come from it |
| an org, project, environment or period | `--org`, `--project` (slug or id), `--env`, `--period` |
| nothing about the project | rely on `SENTRY_ORG` / `SENTRY_PROJECT` / `SENTRY_ENVIRONMENT`, or on what the project context declares (below); ask only if neither exists |
| "for Slack" | `--format slack` |
| a specific issue, or you need the stack of a top issue | `--issue <SHORT-ID>` |
| "is it set up", "check my token", or the first run on a machine | `--doctor` — tools, token, scopes, org and project access, one `ok`/`FAIL`/`skip` line each |

Auth is `SENTRY_AUTH_TOKEN` or the `token=` line of `~/.sentryclirc`. A project with
100 issues takes about 10 seconds. Do not parallelize or paginate it yourself. On
Windows run it from Git Bash exactly as above (never PowerShell); `curl` ships with
Git for Windows, `jq` comes from `winget install jqlang.jq` — `--doctor` says which
one is missing.

Show the table **verbatim** first — one row per issue, then the `Clusters` block. Column
semantics, the score formula and the origin rules: [reference.md](reference.md).

## Step 2 — add the complexity call and the priority order

Severity alone puts noise first (a `browser / CustomEvent` cluster hit by 30 users is
severe and worthless). Priority is severity **and** cost, so after the table produce a
short ranked list, top 5 to 10, with one line per entry:

```
1. [SHORT-ID or cluster] — severity <sev> · complexity <S|M|L|noise> — <what to do, one clause>
```

Complexity rubric — decide from `Origin`, `Where`, the cluster and, for the top entries,
`--issue` output (frames innermost first, release / browser / url breakdown):

| Signal | Complexity | Typical action |
|---|---|---|
| `app`, one in-app file, single release in tags | **S** | regression from that release — read the frame, guard or revert |
| `app`, one file, several releases | **M** | real defect, local fix |
| a cluster of N `app` issues on the same file, or `network / API Error: 401` × N | **M**, fix once | one root cause: auth/session handling, a shared hook |
| `vendor` package, no in-app frame | **M–L** | upgrade, pin, or wrap the call; check the package changelog |
| `browser` (`CustomEvent`, `[object Event]`, chunk / script load) | **noise** unless users cannot proceed | drop via SDK `ignoreErrors` / `beforeSend`, or fix the asset path if it is a deploy artefact |
| `network` 5xx / timeouts | **not front-end** | route to the backend owner, link the issue |
| single browser or single user in tags | **S or noise** | browser-specific; decide by user count |

When the project context lets you resolve `Where` to a file in the working tree, open
that file at the line before assigning S/M/L — a one-line guard is S, a missing provider
in a routing tree is M. Never guess a fix from the title alone.

## Project context

This skill assumes nothing about a company, a stack or a repository. Anything the
host project declares — in its `CLAUDE.md`, `AGENTS.md` or equivalent — wins over the
defaults here. Useful declarations:

```markdown
## Sentry
- org `acme`, project `web` (id 123), environment `prod`
- `Where` paths are relative to `packages/<app>/src`; `dist/client/proxy-client.js` is the shared API client in `packages/lib-api`
- known noise, do not rank: `[object HTMLLinkElement]`, `ResizeObserver loop`
- 401 clusters belong to the auth team; open a ticket in AUTH instead of fixing
- tickets: one Jira per cluster, key prefix WEB-
```

Apply such rules silently: filter what it calls noise out of the ranked list (keep it
in the raw table), map paths to files, name the owner it names.

## Failures

The script exits non-zero with the cause on its **last** stderr line: no token, token
rejected, unknown org / project / issue, an HTTP error from Sentry. Relay that line and
stop. Never produce a ranking from a partial table or from memory of the Sentry UI.
