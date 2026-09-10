# PR to-do — full reference

## Columns

| Column | Values |
|---|---|
| PR | `[repo#N](url)` — clickable |
| Role | `author`, `assignee`, `reviewer` (requested directly), `reviewer(team)` (requested through a team), comma-joined |
| Status | `draft`, `conflict`, `ci-failing`, `behind`, `blocked`, `ready`, `unknown` |
| Blockers | see below, or `-` when nothing blocks |
| Age | days since the PR was last updated |
| Title | truncated to 60 characters |

`unknown` is not a bug: GitHub computes mergeability lazily, so a PR nobody has
touched recently has no answer yet. It resolves itself on a later run.

## Blockers

`conflicts` · `ci: <failed check names>` · `ci: pending` ·
`changes requested: <logins>` · `N unresolved threads` ·
`awaiting review: <logins or teams>` · `review required` · `needs approval` ·
`behind base`

Two of these deserve explanation.

**`needs approval`** is a non-draft PR that GitHub reports as `BLOCKED` with no
other visible cause. In practice that is a branch-protection rule — usually
CODEOWNERS — waiting for a human approval. GitHub exposes no review decision for
that state, so it can only be inferred from the absence of every other cause. A
draft with nothing else wrong shows `-` instead: the `draft` status is the whole
story, and labelling it twice helps nobody.

**`changes requested: you`** means the reported developer is the one who
requested the changes. On a re-requested review that is their own earlier verdict
coming back around, not someone else's objection.

## Bots are excluded from `awaiting review`

Any requested reviewer whose login ends in `bot` or `[bot]` is dropped. Their
approval is automatic, so listing them as something a human is waiting on is
noise.

## Why your own PRs may show as `assignee`, never `author`

In organizations where a bot opens pull requests from pushed commits, the bot is
the GitHub author and the developer is set as assignee. A report that searched
`author:` alone would come back empty for a developer whose every PR is their
own work. All three roles are searched, which is why the report is correct in
those organizations and in ordinary ones alike.

If you have never seen this, it is because your organization has no such bot.
The behaviour costs nothing when it does not apply.

## Why two GitHub passes

GitHub computes `mergeable` and `mergeStateStatus` lazily — roughly 7 seconds per
25 pull requests — and a search that asks for them alongside reviews and check
runs answers HTTP 502 or an empty body.

So the script runs two passes:

1. one paginated GraphQL search per role (review-requested, author, assignee),
   in parallel, reading only cheap fields
2. mergeability for the unique PR ids, in parallel batches of 25 through
   `nodes(ids:)`

Pages of 25 and three attempts per role absorb the remaining flakiness. Any role
that fails all three times aborts the report rather than returning a partial
to-do list.

## Automated invocation

The report is a plain script, so it runs on a schedule with no agent session:

```bash
GH_TOKEN=<token with read access to the org's pull requests> \
PR_TODO_ORG=<org> \
  bash skills/pr-todo/scripts/pr-todo.sh --user <login> --format slack
```

The mrkdwn output is ready to post as a single Slack message. Nothing hardcodes a
login, a team or a channel: the caller supplies the developer.

## Portability

The logic lives in bash, `gh` and `jq`, not in prose an agent has to interpret, so
it behaves identically under any agent that can run a shell. Agent Skills is an
open standard (<https://agentskills.io/>) implemented by Claude Code, Codex and
ChatGPT, Cursor, Gemini CLI, Copilot and others.
