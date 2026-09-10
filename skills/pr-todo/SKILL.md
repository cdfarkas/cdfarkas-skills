---
name: pr-todo
description: >
  Report every open pull request a developer must act on in a GitHub organization —
  review requested, authored, or assigned — as a raw table with clickable links, merge
  status, the concrete reason each PR is stuck, and age. Use when someone asks which PRs
  are waiting on them, what reviews they owe, why their PRs are not merging, or wants that
  list for another developer or formatted for Slack. Needs the gh CLI and jq.
license: Apache-2.0
---

# PR to-do

One script produces the whole report. Run it, return its output **verbatim** — no
summary, no commentary, no reformatting. The reader wants the table, nothing else.

## Run it

```bash
bash <skill-dir>/scripts/pr-todo.sh [--user <login>|@me] [--org <org>] [--format md|slack]
```

`<skill-dir>` is the directory holding this file. Map what the caller said to flags:

| Caller says | Flag |
|---|---|
| nothing, "my PRs", `@me` | no `--user` — the authenticated `gh` login is used |
| a GitHub login | `--user <login>` |
| "for Slack", "to paste in a message" | `--format slack` |
| an organization name | `--org <org>` |

The organization has no default. Pass `--org`, or set `PR_TODO_ORG` once in the
environment so callers never have to name it.

Requires `gh` (authenticated, read access to the organization's repositories) and `jq`.
A developer with about 100 open PRs takes 10 to 30 seconds. Do not parallelize or retry
it yourself: it already runs its GitHub queries concurrently and retries flaky pages.

## What comes back

A header line, then one row per PR — a markdown table by default, mrkdwn bullets with
`--format slack` — or `nothing to do`. Rows are sorted with the developer's own PRs first,
then the reviews they owe, oldest first within each group.

Full column reference, status vocabulary and failure modes: [reference.md](reference.md).

## Failures

The script exits non-zero and names the cause on its **last** stderr line: `gh` not
authenticated, a login that does not exist, a search that failed three times, a
mergeability batch that failed. Earlier lines, when there are any, are retry notices
(`search <role>: attempt 2/3 failed, retrying`) or the usage block after a bad flag.
Relay the last line as-is and stop. Never emit a partial table, a stale one, or an invented
one — a to-do list that quietly drops PRs is worse than no list.
