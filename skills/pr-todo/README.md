# pr-todo

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

## Usage

```
bash scripts/pr-todo.sh --org <org> [--user <login>] [--format md|slack]
```

`--format slack` gives the same thing as mrkdwn bullets, ready to paste.
`--user <login>` reports on someone else. `PR_TODO_ORG` saves the flag. Needs `gh`
(authenticated) and `jq`. Columns, status vocabulary and failure modes:
[`reference.md`](reference.md).

## Evaluation

Scores: 7/7, 6/6 and 3/3 on its assertions with the skill; 2/6 and 0/3 on the two
baselines that completed without it. Full numbers and method in
[`evals/RESULTS.md`](evals/RESULTS.md).
