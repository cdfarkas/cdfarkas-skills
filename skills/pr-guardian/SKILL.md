---
name: pr-guardian
description: >
  Watch one pushed branch in the background until its pull request is green, merged or
  blocked: a guardian agent rebases on the default branch, fixes what CI and the reviewers
  report, commits and pushes per the repo's configured policy, and reports with proof. One
  guardian per branch, a write lock so a human and the agent never race on the same push,
  and re-adoption of the branches whose guardian died with its session. Use when someone
  says "watch my PR", "babysit this branch until green", "is my branch mergeable", "keep
  this PR mergeable", or right after a push. `--dry-run` prints the diagnosis and the action
  plan without pushing anything. Also checks the prerequisites and offers to install or
  configure what is missing: "set up pr-guardian", "check my setup", "is my machine ready".
  Needs git, gh (authenticated, repo scope), jq, coreutils timeout and bash 3.2 or newer —
  Git Bash on Windows.
license: Apache-2.0
---

# PR guardian

Three entry points, one script and one agent. `<skill-dir>` is the directory holding this
file; the script is `scripts/pr-guardian.sh` (`--help` lists every command), the agent is
`agents/pr-guardian.md`, dispatched as `subagent_type: "pr-guardian"`.

| Caller says | Do |
|---|---|
| "set up pr-guardian", "check my setup", "is my machine ready", `doctor` | the **setup** procedure below: `doctor`, then `doctor --fix` and `config init` as proposals. |
| "watch my PR", "babysit this branch", "keep it mergeable", `watch [<branch>] [--dry-run]` | the **watch** procedure below. No branch named: the current one. |
| "is my branch mergeable", "what would the guardian do", `watch --dry-run` | **watch** with `--dry-run`: the agent runs `doctor` and `plan`, prints the action list, pushes nothing, and ends with `DRY-RUN`. |
| "which guardians are running", `status` | `bash <skill-dir>/scripts/pr-guardian.sh list`, then one `plan --repo <repo> --branch <branch>` per live entry; relay both. |

## setup

1. `bash <skill-dir>/scripts/pr-guardian.sh doctor`. Relay its lines verbatim, one `ok` /
   `FAIL` / `skip` per check; every check runs, the exit code is 1 when any failed.
2. No `FAIL`: say in one line that the machine is ready, then go to step 5.
3. Any `FAIL`: `bash <skill-dir>/scripts/pr-guardian.sh doctor --fix`. It runs nothing; it
   prints one `fix: <command>` per failed check whose hint is a command. Present each one
   as a proposal and run only what the user approves, never an install command of your
   own. `gh auth login` is interactive: the user runs it in their own terminal. On Windows
   say the command may need an elevated terminal. A `FAIL` with no `fix:` line (`shell`,
   `state`) is fixed by hand as its hint says.
4. After a fix, run `doctor` again and relay it. Stop while a `FAIL` remains.
5. Propose `bash <skill-dir>/scripts/pr-guardian.sh config init --dir <repo>` in one line
   (`exists: <path>` means the repo already has one; `--dry-run` shows the file) and ask
   two things: does a bot open the PRs (then `pr.create` is `false`) and does the team
   squash-merge (then `commits` is `"amend"`). Explain a key with its row in the table
   below, one line each, when the user asks or answers.

## watch

1. `bash <skill-dir>/scripts/pr-guardian.sh doctor`. On a `FAIL` line, relay it and stop —
   nothing is dispatched until it passes; the **setup** procedure is the way to fix it.
2. Resolve the target: `repo` as `owner/name` from `git remote get-url origin`, `branch`
   (the argument, else `git rev-parse --abbrev-ref HEAD`), `worktree` from
   `git rev-parse --show-toplevel`, HEAD from `git rev-parse --short HEAD`.
3. Register the entry and keep the id it prints:
   `bash <skill-dir>/scripts/pr-guardian.sh register --repo <repo> --branch <branch> --worktree <worktree> --sha <head>`.
   If the same script's `get --repo <repo> --branch <branch>` already shows a `live` entry
   with an agent, do not dispatch a second one: `SendMessage` that agent instead.
4. Dispatch the agent, in the background, with a brief that carries verbatim: `repo`,
   `branch`, `worktree`, `guardian id`, `script: <skill-dir>/scripts/pr-guardian.sh`, HEAD
   and its subject, your own agent handle, `--dry-run` when asked, and the acceptance:
   *PR mergeable, every required check green, no unresolved review thread.*
5. Right after the Agent tool returns, record the handle — an unregistered guardian is
   unreachable: `bash <skill-dir>/scripts/pr-guardian.sh set --id <id> --agent "<handle>"`.
   Tell the user in one line that the guardian is running and how to reach it.
6. When the agent reports, relay its first line (`GREEN`, `MERGED`, `BLOCKED`,
   `UNREVIEWED` or `DRY-RUN`) and the PR URL, then what needs a human. Subagent output
   never reaches the user on its own.

The plugin's hooks do steps 2 to 5 for you after every successful `git push` on a
`feat/`, `fix/`, `chore/`, `refactor/`, `perf/`, `docs/`, `ci/` or `test/` branch, and
list the orphaned guardians at session start. This procedure is for a branch pushed
before the plugin was installed, a guardian someone stopped, or a dry run.

## Configuration

Read from `<repo>/.pr-guardian.json`, else `~/.config/pr-guardian.json`, else the default.
`bash <skill-dir>/scripts/pr-guardian.sh config <key> --dir <repo>` prints the value in force;
`config init --dir <repo>` writes the file with the defaults when the repo has none.

| Key | Default | Effect |
|---|---|---|
| `orgs` | `[]` (any owner) | The hooks act only on repositories whose owner is listed; a manual `watch` ignores it. |
| `pr.create` | `true` | The guardian opens the PR when none exists. `false`: it never runs `gh pr create` and waits for one. |
| `commits` | `"stack"` | Fixes are new commits; `--force-with-lease` only after a rebase. `"amend"`: every fix is amended into the branch's single commit. |
| `pr.sync_body` | `false` | `true`: after an amend that rewrote the message, the PR body (and title) are rewritten from the head commit. |
| `review_bots` | `[]` | Logins whose conversation comments count as review findings and must cover HEAD before the PR is `GREEN`. |

A team whose bot opens the PR from the pushed commit, squash-merges, and builds the
description from the commit body:

```json
{ "orgs": ["my-org"], "pr": { "create": false, "sync_body": true }, "commits": "amend", "review_bots": ["review-bot[bot]"] }
```

## Prerequisites

`bash <skill-dir>/scripts/pr-guardian.sh doctor` — bash 3.2+, git, gh authenticated with the
`repo` scope, jq, coreutils `timeout`, Git Bash on Windows, a writable state directory
(`$PR_GUARDIAN_HOME`, default `~/.pr-guardian`). One line per check, every check runs, exit
1 when any `FAIL`, each with the install command for the OS; `doctor --fix` lists those
commands as `fix:` lines and runs none of them.

State file, lock semantics, hook events, `plan` lines, report vocabulary and every failure
line: [reference.md](reference.md).
