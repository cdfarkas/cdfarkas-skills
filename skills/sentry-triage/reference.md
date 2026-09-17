# Sentry triage — full reference

## Header

`Sentry triage · <org>/<project> · <env> · <period> · <query> · N issues`

## Columns

| Column | Values |
|---|---|
| Issue | `[SHORT-ID](permalink)` — clickable |
| Sev | `critical` (score ≥ 400), `high` (≥ 150), `medium` (≥ 40), `low` |
| Score | the number the buckets come from, see below |
| Users | distinct users hit over the period (`userCount`) |
| Events | events over the period |
| Trend | `↑` last third of the period > 1.5× the third before it (and ≥ 5 events), `↓` < 0.5×, `→` otherwise |
| Status | Sentry substatus: `new`, `escalating`, `regressed`, `ongoing` |
| Origin | `app`, `vendor`, `network`, `browser` — see below |
| Where | innermost in-app frame `path:line function`; the innermost code frame when no in-app frame; `-` when the latest event has no code frame at all |
| Title | truncated to 60 characters |

Rows are sorted by score, then users, descending.

## Score

```
score = (users × 10 + events) × level × unhandled × status
level:     fatal 2 · error 1 · warning 0.5 · info/debug 0.2
unhandled: 1.5 when Sentry flags the exception unhandled, else 1
status:    escalating 1.5 · regressed 1.3 · new 1.2 · ongoing 1
```

Users weigh ten times events on purpose: 100 events from one user is one broken
session, 20 events from 20 users is a bug everyone hits. An issue with zero users is
not free — `userCount` is 0 when the SDK never identified anyone, typically before
login — but it ranks below anything with named users at equal volume.

The thresholds are fixed, not quantiles, so a project's ranking does not move when
another issue appears. They were set on a React front-end with ~30 unresolved issues
and 1–25 users each; a project with thousands of users per issue will read `critical`
on every row and should sort by Score instead.

## Origin

Decided from the title and exception value first, then the frames, in this order:

1. **browser** — the message is a browser event captured as an exception, or an asset
   that failed to load: `CustomEvent`, `[object Event]`, `[object HTML…Element]`,
   `Loading chunk`, `ChunkLoadError`, `Failed to load script`, `Federation Runtime`,
   `Script error`, `ResizeObserver`, `Non-Error promise rejection`.
2. **network** — an HTTP failure surfaced as an error: `API Error`, `ApiClientError`,
   `Failed to fetch`, `NetworkError`, `Load failed`, `status code 4xx/5xx`, a bare
   `401`/`403`/`404`/`429`/`5xx`, timeouts, `AxiosError`.
3. **app** — the innermost code frame Sentry marks `inApp`.
4. **vendor** — no in-app frame; every code frame is under `node_modules/`.

A `network` issue whose `Where` is an in-app hook is still `network`: the hook is
where the failed call was awaited, not where it failed.

## Clusters

Issues that share one root cause, listed when the group has more than one member:

- `network / <status or message>` — same HTTP failure (`API Error: 401`, `Failed to fetch`)
- `vendor / <package>` — same third-party package, taken from the innermost `node_modules/` frame
- `browser / <message kind>` — same browser-level message
- `app / <file>` — same innermost in-app file

Each line carries the member count, users, events, summed score and the short ids.
A cluster's summed score is the argument for fixing it once instead of picking its
members off one by one.

## `--issue` output

```
<SHORT-ID> · <sev> <score> · <origin> · <permalink>
<title>
value: <exception value>
users N · events N <trend> · <status> · level · unhandled · first <date> (age) · last <date> · latest release
Frames, innermost first:  up to 12, [app] marks in-app frames
Tags:                     top 5 values per requested key, with counts
Daily events:             one number per day of the period
```

`--tags` accepts any tag key the project sends (`release`, `browser`, `url`,
`transaction`, `os`, custom ones). A single value under `release` with the issue
`first` date matching that release is the strongest regression signal there is.

## `--doctor` output

One line per check, in order, stopping at the first failure (exit 1):

```
ok    curl: /usr/bin/curl
ok    jq: /opt/homebrew/bin/jq
ok    token: SENTRY_AUTH_TOKEN          (or ~/.sentryclirc)
ok    auth: <email> on https://sentry.io
ok    scopes: org:read project:read event:read …
ok    org: <slug>                       (skip when none given)
ok    project: <slug> (<id>)            (skip when none given)
ok    issues: readable in <env>
```

It installs nothing and opens no login flow: a `FAIL` line says what to set, and the
run stops there.

## Failures

Every failure exits non-zero and names the cause on the last stderr line:

- `no Sentry token: set SENTRY_AUTH_TOKEN or put token= in ~/.sentryclirc`
- `Sentry rejected the token (HTTP 401) on <path>`
- `no access to <path> (HTTP 403) — wrong org slug, or the token lacks the scope`
- `unknown project '<slug>' in organization <org>` / `unknown project id <id> …`
- `unknown issue '<id>' in <org>/<project>`
- `issue <id> has no event matching <period> in <env> on project <project>`
- `Sentry answered HTTP <status> on <path>: <body excerpt>`

The latest event of one issue failing to load does not abort the run: that issue is
kept with `Where` = `-` and its origin decided from the title alone.

## Windows

The script runs under Git Bash, which is the shell Claude Code uses on Windows. `curl`
comes with Git for Windows; install `jq` with `winget install jqlang.jq` (or scoop /
chocolatey). `.gitattributes` forces LF endings on the scripts so a checkout with
`core.autocrlf=true` does not break them; a `~/.sentryclirc` saved with CRLF is read
correctly. PowerShell is not supported and not needed.

## Token scope

A Sentry auth token with `org:read`, `project:read` and `event:read` is enough.
Self-hosted Sentry: set `SENTRY_URL` to the instance root.
