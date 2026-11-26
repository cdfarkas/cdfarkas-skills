# cdfarkas-skills — working rules

Public repository. Every skill ships with the evidence it works; nothing personal or
company-specific goes in (CI greps for `/Users/…` and `/home/…`).

## Evidence

No agent or skill is added or changed without recorded evidence: runs with and without it, the
date, the model, the scores, the failures, and what was not measured. A claim without evidence
is marked **unverified**. A trial that both arms pass fully proves nothing: make it harder
before running it again.

For a skill the record is `skills/<name>/evals/RESULTS.md` (rules 2 and 3 below). For an agent
under `agents/`, candidates included, it is the `RESULTS.md` of its trial in
`agents/trials/<trial>/`, which names the agent file by its path in backticks.
`validate-evals.py` checks that the name is there, not that the evidence is good.

## Decisions

One ADR per major decision, in `docs/adr/` (copy `0000-template.md`). The PR that accepts or
supersedes one updates the living docs and cites the ADR in force there: `CLAUDE.md`, `README.md`,
`agents/README.md`, `docs/how-these-skills-are-built.md`. An accepted ADR is never edited or
removed: a new one supersedes it, and only its Status changes.
`python3 scripts/check-adr.py origin/main` enforces it.

Agents start from existing ones and are trialled before being kept (ADR 0001).
Profession knowledge goes in a skill; an agent file exists only for a mechanical reason it states,
and work is split by context, not by type of work (ADR 0003). Its rules change only after reading the
latest primary sources, which the superseding ADR lists with the date read.
The tool of the improvement loop is public, the record of errors stays outside this repository (ADR 0002):
no ledger, no row of a real error, invented examples only.

## Before a skill is committed

1. **Behaviour in a script, not in prose.** If two agents could read a sentence and
   produce different output, it is code, not a sentence. `SKILL.md` says when to run
   the script and how to read its output. See `docs/how-these-skills-are-built.md`.
2. **Evaluate with `skill-creator`, with-skill versus without-skill.** Use the
   `skill-creator` skill (Anthropic's first-party plugin) to run every prompt in
   `skills/<name>/evals/evals.json` with a subagent that has the skill and one that does not,
   in isolated sessions, and grade both with the skill's own `evals/grade.py`. Run each arm
   more than once, on more than one model when possible, and mark a single-run result as such.
   Check that the skill triggers on its eval prompts and not on unrelated ones.
   Prompts must be what a real person would type. A skill that scores the same as the
   baseline is decoration and does not ship. Keep a skill small and focused, and a change
   the improvement loop proposes is decided by a person (ADR 0003).
3. **Publish the evaluation in `evals/RESULTS.md`**, in the shape of
   `skills/pr-todo/evals/RESULTS.md`: method, the run date, a scores table
   (with the skill / without), what the baselines got wrong, and every run that did
   not complete reported as **not measured** — never as a zero. If the run is not
   done yet, `RESULTS.md` says so; an absent or flattering results file is a defect.
4. **Run the CI locally** (`python3 scripts/validate-skills.py`,
   `python3 scripts/validate-evals.py`, `python3 scripts/check-docs-sync.py origin/main`,
   `python3 scripts/check-adr.py --self-test`, `python3 scripts/check-adr.py origin/main`,
   `python3 agents/trials/data/bench.py selftest`, `python3 agents/loop.py selftest`,
   `python3 agents/loop.py size` (tracked files only, so `git add` a new agent first; it also
   refuses a `.jsonl` file outside `skills/`),
   `bash -n` on every `.sh`, the personal-path grep) before committing; the `windows`
   job in `.github/workflows/ci.yml` needs a PR to run, so open one. Plugins carry no
   `version` field and Claude Code tracks them by commit SHA, so no version bump is needed
   (never add a `version` field to an entry: it would pin users until bumped). A script
   that pushes, edits a PR or calls a write endpoint takes `--dry-run`
   (`validate-skills.py` refuses it otherwise; rule 4 of the docs says why).
5. **Docs follow the code.** Any change to a skill's `scripts/`, `hooks/`, `agents/` or
   `SKILL.md` updates its `README.md` or `reference.md` in the same PR (a
   `package-lock.json` change, or a `package.json` change confined to its dependency
   maps, excepted); a change to
   `scripts/*.py` or `.github/workflows/ci.yml` (a bump of an action's version alone
   excepted) updates this file or
   `docs/how-these-skills-are-built.md`; a plugin added to or removed from the
   marketplace manifest changes the root `README.md` table. `scripts/check-docs-sync.py`
   enforces it, and always checks that every skill has its three Markdown files, its row
   in the root table, and names its `agents/` and `hooks/` when it ships them.

## Layout of a skill

```
skills/<name>/
  SKILL.md          frontmatter (name = directory, description ≤ 1024 chars) + body < 500 lines
  README.md         usage, sample output, evaluation — for humans
  reference.md      columns, vocabularies, failure lines — what SKILL.md points to
  scripts/          the implementation; bash 3.2 compatible, LF endings, runs under Git Bash
  evals/evals.json  prompts + assertions
  evals/grade.py    regex grader, no model in the loop
  evals/RESULTS.md  the published run
  evals/reserved.txt  optional: the checks kept for the gate of `agents/loop.py`, one per line
  agents/           optional: a plugin that ships a background agent (one .md per agent)
  hooks/            optional: the scripts of the Claude Code hooks a plugin ships
```

Register the skill in `.claude-plugin/marketplace.json`, give it a `README.md` in its folder (usage, sample output, evaluation) and one row in the root `README.md` table.

A plugin that ships hooks declares them inline, as the `hooks` object of its marketplace entry
(event name to array of matcher groups): Claude Code refuses a file path there, and
`claude plugin validate` does not report it. `validate-skills.py` checks the shape and that every
`${CLAUDE_PLUGIN_ROOT}/…` script a command names exists.

## Agents and their trials

`agents/` holds the trials that compare an agent with the generalist and the loop that improves
an agent or a skill without growing its file: steps, commands and isolation limits in `agents/README.md`.
An agent file is at most 1,500 words and a `SKILL.md` body at most 500 lines. A file that was
already longer has its own ceiling in `CEILINGS` (`agents/loop.py`), which may only go down.

## Checking legal sources

Skills that rely on official legal pages list them in `skills/<name>/sources.json` (id, url,
quote of at most 300 chars, retrieved date, status `read` or `unread`). The owner runs
`python3 scripts/check-sources.py` by hand (stdlib only, writes nothing; `--json`, skill names
to restrict, `--root` for another tree, `--self-test` offline). It fetches each distinct URL
once with a plain client and reports per source:

- `CHANGED`: the page was fetched and the quote is missing (exit 1). Update the skill and the
  source's quote and `retrieved` date in the same PR.
- `UNREACHABLE`: 4xx/5xx, timeout, empty or bot-protection body. Retry later.
- `BLOCKED`: the site refuses automated clients (legifrance.gouv.fr answers 403, eur-lex 202 empty).
- `UNREAD`: the manifest says the page was never read; a reminder.
- `UNCHANGED`: quote found. An invalid manifest exits 2.

For each `BLOCKED` source, open it from Claude with a web-fetch tool and ask whether the page
still contains the quote and, for Légifrance, whether the article version is still "en vigueur"
(an amended article gets a new LEGIARTI id, so an old URL shows an outdated version instead of
failing). That web-fetch check is model-judged, not exact: treat a doubtful answer as a reason
to open the page yourself.
