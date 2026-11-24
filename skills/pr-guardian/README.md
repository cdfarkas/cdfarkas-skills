# pr-guardian

A background agent that keeps one pushed branch mergeable until its pull request is
green, merged or blocked: it rebases on the default branch, fixes what CI and the
reviewers report, commits and pushes per the repo's configured policy, and reports
with proof. One guardian per branch, a write lock so the human and the agent never
race on the same push, and re-adoption of the branches whose guardian died with its
session.

## Usage

```
/pr-guardian doctor [--fix]
/pr-guardian config init [--user] [--dir <repo>] [--set <key>=<json>]... [--dry-run]
/pr-guardian watch [<branch>] [--dry-run]
/pr-guardian status
```

`doctor` checks the prerequisites, one line per check; every check runs and the exit code
is 1 when any of them failed:

```
ok    bash: 5.3.9(1)-release
ok    git: /usr/bin/git
ok    gh: /opt/homebrew/bin/gh
ok    gh auth: cdfarkas
ok    scopes: read:enterprise, read:org, read:user, repo, user:email, workflow, write:discussion
ok    jq: /opt/homebrew/bin/jq
ok    timeout: /opt/homebrew/bin/timeout
ok    shell: bash on Darwin
ok    state: ~/.pr-guardian
```

A failed check names its cause and the command that fixes it, `FAIL  jq: not installed
(brew install jq)`. `doctor --fix` prints those commands back as `fix: brew install jq`
lines and runs none of them (`nothing to fix` when every check passed): the agent shows each
one as a proposal and runs only what you approve; `gh auth login` is interactive, so you run
it yourself. `config init` writes the keys you give it to `.pr-guardian.json` at the repo
root and prints the path, `exists: <path>` when the repo already has one, `nothing to write:
<path>` when no key is given, and with `--dry-run` prints the file instead of writing it.
`config init --user` does the same for `~/.config/pr-guardian.json`, your own settings for
every repository, and leaves out a value equal to its default:

```bash
bash scripts/pr-guardian.sh config init --user --set 'orgs=["my-org"]' \
  --set 'branch_prefixes=["feat","fix","chore","refactor","perf","docs","ci","test","my-login"]'
bash scripts/pr-guardian.sh config init --dir <repo> --set pr.create=false --set 'commits="amend"'
```

The setup conversation is: `doctor`, the `fix:` proposals, `doctor` again, then, when you
have no user file, `config init --user` with two questions — which owners' repositories the
hooks may act on (`orgs`), which extra branch prefixes you push (`branch_prefixes`) — and
`config init` with two more — does a bot open your PRs (`pr.create=false`), does the team
squash-merge (`commits="amend"`). Both files are optional, each is written only after you
approve its `--dry-run` output, and no hook writes either one.

`watch` registers the branch and dispatches the agent in the background; with
`--dry-run` the agent runs the read-only diagnosis, prints the actions it would take
and pushes nothing. The diagnosis is `scripts/pr-guardian.sh plan`, here on two branches
of this repository — one not yet opened as a PR, one merged:

```
pr: none open for chore/docs-sync-check on cdfarkas/cdfarkas-skills (base main)
next: open a PR from chore/docs-sync-check onto main
```

```
pr: #7 https://github.com/cdfarkas/cdfarkas-skills/pull/7 draft=false mergeable=UNKNOWN state=UNKNOWN
next: nothing — PR is MERGED
```

`status` lists the live guardians and one `plan` per entry. After every successful
`git push` on a branch under one of the `branch_prefixes` (by default `feat/`, `fix/`,
`chore/`, `refactor/`, `perf/`, `docs/`, `ci/` and `test/`) the plugin's hooks do the
`watch` for you; the command is for a branch pushed before the plugin was installed, a
guardian someone stopped, or a dry run.
State file, lock semantics, `plan` lines, report vocabulary and every failure line:
[`reference.md`](reference.md).

## Configuration

Merged key by key: the defaults, then `~/.config/pr-guardian.json`, then
`<repo>/.pr-guardian.json`. `bash scripts/pr-guardian.sh config <key> --dir <repo>` prints
the value in force. A key present in the repository file wins even at its default value:
remove it from there to let your own setting apply.

| Key | Default | Effect |
|---|---|---|
| `orgs` | `[]` (any owner) | The hooks act only on repositories whose owner is listed; a manual `watch` ignores it. |
| `branch_prefixes` | `["feat", "fix", "chore", "refactor", "perf", "docs", "ci", "test"]` | After a push, the hook dispatches only on a branch named `<prefix>/…` (without the slash here, matched literally), never on the default branch; a manual `watch` ignores it. The value replaces the default list: `["feat", "fix", "my-login"]`. |
| `pr.create` | `true` | The guardian opens the PR when none exists. `false`: it never runs `gh pr create` and waits for one. |
| `commits` | `"stack"` | Fixes are new commits; `--force-with-lease` only after a rebase. `"amend"`: every fix is amended into the branch's single commit. |
| `pr.sync_body` | `false` | `true`: after an amend that rewrote the message, the PR body (and title) are rewritten from the head commit. |
| `review_bots` | `[]` | Logins whose conversation comments count as review findings and must cover HEAD before the PR is `GREEN`. |

A team whose bot opens the PR from the pushed commit, squash-merges, and builds the
description from the commit body:

```json
{ "orgs": ["my-org"], "pr": { "create": false, "sync_body": true }, "commits": "amend", "review_bots": ["review-bot[bot]"] }
```

## What ships

- `agents/pr-guardian.md` — the guardian agent, dispatched as `subagent_type: "pr-guardian"`. Its frontmatter says `model: inherit`: it runs on whatever model the dispatching session uses, the plugin does not pick one for you.
- `hooks/` — the scripts of four Claude Code hooks, declared in the plugin's entry of `.claude-plugin/marketplace.json`: `PreToolUse` on `Bash` (`lock-guard.sh`, blocks a `git commit` / `git push` on a branch whose lock someone else holds), `PostToolUse` on `Bash` (`dispatch.sh`, registers the branch and hands you the dispatch brief after a push), `SessionStart` (`adopt.sh`, runs `doctor` and lists the orphaned guardians), `SessionEnd` (`session-end.sh`, releases the session's locks and marks its guardians adoptable).
- `scripts/pr-guardian.sh` — state, lock, config, `plan` and `doctor`; `--help` lists every command. `scripts/git-target.sh` resolves the repo and branch a `git` command acts on, for the hooks.

## Prerequisites

git, `gh` authenticated with the `repo` scope, `jq`, coreutils `timeout`, bash 3.2 or
newer — Git Bash on Windows. `doctor` checks each one and prints the install command for
the OS on a `FAIL`; `doctor --fix` lists those commands for the agent to propose.

## Evaluation

Scores: 5/5, 5/5 and 4/4 on its assertions with the skill; 2/5, 2/5 and 1/4 without,
in 22 s against 308 s of mean wall-clock. Three prompts on the setup path (everything
installed, `jq` missing, `gh` not authenticated), offline, with the harness controlling
`PATH` and `GH_CONFIG_DIR`, graded by regex. Full numbers, the contaminated first
baseline run and the two assertion fixes in [`evals/RESULTS.md`](evals/RESULTS.md).
The watch loop itself (rebase, CI fixes, review triage) is not covered: it needs a live
pull request, and the same code runs unchanged as a private guardian; what this public
skill adds, and what is evaluated, is the setup.
