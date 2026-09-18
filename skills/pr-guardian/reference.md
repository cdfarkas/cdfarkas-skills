# PR guardian — full reference

Everything below is read from `scripts/pr-guardian.sh` and the four hooks; the script's
`--help` is the command list.

## State

`$PR_GUARDIAN_HOME` (default `~/.pr-guardian`) holds `state.json`, `locks/` and
`pr-guardian.log`. Never hand-edit `state.json`; a file that does not parse is replaced by
an empty registry on the next command.

```json
{ "version": 1, "guardians": [ <entry>, … ] }
```

One entry per repo+branch that is not `done`:

| Field | Value |
|---|---|
| `id` | `grd_<unix epoch>_<random>`; the epoch is what `prune` ages entries on |
| `repo`, `branch` | `owner/name` and the branch ref |
| `worktree` | the checkout the guardian writes in (`--worktree`, empty when unknown) |
| `agent` | the handle the Agent tool returned, recorded with `set --agent`; empty shows as `UNREGISTERED` in `list` |
| `session_id` | the session that registered or refreshed the entry |
| `pr` | PR number as a string, empty until `set --pr` |
| `last_sha` | the HEAD the guardian last read |
| `status` | `live` — a guardian is on it · `orphaned` — its session ended before the PR was confirmed green (`orphaned_at` set) · `done` — PR merged or guardian finished; hidden from `get` and `list` |
| `pushes` | how many times `register` was called for it |
| `notes` | `[{ "at": <utc>, "text": <note> }]`, appended by `set --note` |
| `created_at`, `updated_at`, `orphaned_at` | UTC timestamps |

`get --session <id>` reports a `live` entry owned by another session with `status: "lost"`
without writing it; `list --session <id>` hides entries owned by other sessions.

`register` on an existing repo+branch refreshes it (status back to `live`, `pushes` + 1,
the fields passed) and prints the same id. `done` marks every non-done entry for the
repo+branch `done` and releases the lock. `prune [--max-age-days N]` (default 7) drops
`done` entries, entries whose id epoch is older than N days, and lock directories older
than N days.

## Lock

`locks/<slug>.lock/` — one directory per repo+branch, created atomically with `mkdir`,
holding a `holder` file (first line the holder string, second the UTC time). The slug is
`repo/branch` with `/`, `:`, `@` and spaces turned into `-` and every other character
outside `[A-Za-z0-9._-]` dropped.

- `acquire --repo --branch --holder <who>`: exit 0 and the lock is yours; exit 1 with
  `held by: <who>` on stderr when someone holds it. `--holder` defaults to `guardian`.
- `locked --repo --branch`: exit 0 and the holder on stdout when held, exit 1 when free.
  A lock whose directory is older than 1800 s is released on the spot and reported free.
- `release --repo --branch`: removes it, silently, held or not.

The PreToolUse hook lets a command through when it starts with, or contains,
`PR_GUARDIAN=<holder>` where `<holder>` equals the lock's holder string.

## Configuration

`config <key> [--dir <repo>]` prints the value in force as JSON. Source, first match wins:
`.pr-guardian.json` at the top level of the git repository containing `--dir`, then
`~/.config/pr-guardian.json`, then the default. A file that is not valid JSON prints
`config: <file> is not valid JSON, using defaults` on stderr and falls back. Keys are
merged over the defaults, so a file may set one key only.

`config init [--dir <repo>]` writes `.pr-guardian.json` holding the five defaults at the
top level of the git repository containing `--dir` (in `--dir` itself when it is not a
repository) and prints the path. It never overwrites: `exists: <path>`, exit 0, when the
file is already there. Under `--dry-run` it prints `dry-run: would write <path>: <json>`
and writes nothing.

| Key | Default | Type |
|---|---|---|
| `orgs` | `[]` | array of owner logins; empty means any |
| `pr.create` | `true` | boolean |
| `commits` | `"stack"` | `"stack"` or `"amend"` |
| `pr.sync_body` | `false` | boolean |
| `review_bots` | `[]` | array of logins |

## Hooks (`hooks/hooks.json`)

| Event | Script | Does |
|---|---|---|
| `PreToolUse` on `Bash` | `lock-guard.sh` | When the command is a real `git commit` or `git push` (heredoc bodies and quoted strings ignored; `git -C <path>`, `cd <path> &&` and `env` prefixes resolved) on a repository whose owner passes `orgs`, and the branch's lock is held by someone other than the `PR_GUARDIAN=` caller: returns `{"decision": "block", "reason": …}` naming the holder, the agent to message, and the `locked` / `release` commands. Anything unexpected exits 0. |
| `PostToolUse` on `Bash` | `dispatch.sh` | After a `git push` whose output shows no rejection or error, on a `feat/ fix/ chore/ refactor/ perf/ docs/ ci/ test/` branch of a repository passing `orgs`: `register` (or refresh) the entry, `prune`, then inject either the dispatch brief (repo, branch, worktree, guardian id, script, HEAD, acceptance, `--dry-run` hint, the `set --agent` command) or, when a `live` guardian with a handle already exists, the `SendMessage` to send it. Never blocks. |
| `SessionStart` | `adopt.sh` | Runs `doctor`; on a `FAIL` injects one warning line (`[pr-guardian] prerequisite missing — …`). Then `prune`, and for the 3 most recent entries of other sessions that are `orphaned` or untouched for 45 minutes: a PR that is `MERGED` or `CLOSED` is marked `done`; a mergeable PR with no failing or pending check gets a note and is left alone; anything else has its lock released and is listed under `# Orphaned PR guardians (adopt these)` with worktree, guardian id and last HEAD. |
| `SessionEnd` | `session-end.sh` | For every `live` entry of the ending session: release its lock, `set --orphan` with a note, and on macOS post a notification. Other sessions' entries are never touched. |

## `plan` output

`plan --repo <owner/name> --branch <ref> [--dir <repo>]` reads only, through `gh` and
`git`. Lines, in order:

```
pr: none open for <branch> on <repo> (base <default>)
pr: #<n> <url> draft=<bool> mergeable=<MERGEABLE|CONFLICTING|UNKNOWN> state=<mergeStateStatus>
base: <default>, behind by <n|?> commit(s)
checks: <failing check names|none failing>, <n> pending
review: <login STATE at time|none>, <n> unresolved thread(s)
```

then one `next:` line per action, in this order — `open a PR from <branch> onto <base>`
· `nothing until a PR exists (pr.create is false)` · `nothing — PR is MERGED|CLOSED` ·
`rebase <branch> on <base>` (CONFLICTING, or behind) · `fix check <name>` (one per check
whose conclusion matches FAILURE, TIMED_OUT, CANCELLED, ACTION_REQUIRED or ERROR) ·
`wait for <n> pending check(s)` · `answer the review (<n> unresolved thread(s))` (newest
review is CHANGES_REQUESTED, or a thread is unresolved) · `resync the PR body from the head
commit` (only with `--dir` and `pr.sync_body` true, when the body differs from `git log
-1 --format=%b`) · `nothing — mergeable, checks green, no review pending`.

`behind by ?` means the compare API did not answer; the guardian then fetches and compares
locally.

## Report vocabulary

The agent's first line is exactly one of:

| Verdict | Meaning |
|---|---|
| `GREEN` | mergeable, every required check passed (not skipped), a review covering HEAD is clean, no unresolved thread, body in sync when `pr.sync_body` is on |
| `MERGED` | the PR merged while the guardian watched |
| `BLOCKED` | a human decision is needed: a conflict between two intents, a failure outside the diff, a design finding, three failed attempts on one failure, a dirty worktree, a `doctor` FAIL, a closed PR, or no PR after 5 cycles with `pr.create` false |
| `UNREVIEWED` | everything that ran is green but no review covers HEAD — the report says why (draft, reviewer skipped, bot silent) and what would make it run |
| `DRY-RUN` | the brief asked for the plan only; nothing was written or pushed |

Second line the PR URL, then at most six lines: checks, review state, changes made, what
needs a human.

## `--dry-run`

A global flag, or `PR_GUARDIAN_DRY_RUN=1`. `register`, `set`, `done`, `acquire`,
`release` and `prune` print `dry-run: would <action>` and write nothing; `get`, `list`,
`locked`, `config`, `plan` and `doctor` are unaffected, they never write.

## Failure lines

Exit 1 with the cause on stderr, unless noted:

`register: need --repo and --branch` · `set: need --id` · `acquire: need --repo and
--branch` · `held by: <who>` (acquire refused) · `config: need a key (orgs, pr.create,
commits, pr.sync_body, review_bots)` · `plan: need --repo and --branch` · `plan: cannot
read <repo> (gh repo view failed — auth, name or network)` · `unknown command: <x>`
(exit 2, usage follows) · no command at all prints the usage and exits 1.

`doctor` runs every check and prints one line each, in this order: bash (3.2 or newer),
git, gh, gh auth, scopes (`skip` on a fine-grained token, which reports none), jq, timeout
(or `gtimeout`), shell (Git Bash required on Windows), state (`$PR_GUARDIAN_HOME`
writable). A failed check prints `FAIL  <check>: <cause> (<install command>)` and the
run goes on; the exit code is 1 when any check failed, 0 otherwise. Without `gh` the
`gh auth` and `scopes` lines read `skip  …: gh not installed`; without authentication,
`scopes` reads `skip  scopes: not checked (gh auth failed)`.

`doctor --fix` prints the same lines, then one `fix: <command>` per `FAIL` whose hint is a
command — `brew`, `winget`, `apt` or `dnf` `install …`, `gh auth login`, `gh auth refresh
-s repo` — and runs nothing; `nothing to fix` when no check failed. A `FAIL` on `shell` or
`state` has no `fix:` line: its hint is an action, not a command. On Linux the hint names
both `apt` and `dnf`; the one the distribution has applies.

## Portability

bash 3.2 (macOS default) and 5.x (Git Bash, Linux); `mkdir` as the lock, no `flock`; BSD
and GNU `stat` and `date`; the hooks always run under `bash` explicitly. The Windows CI
job runs `--help` and `doctor` under Git Bash without a token and expects the
`FAIL  gh` line, not a crash.
