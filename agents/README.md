# Agent trials and improvement loop

The scripts measure. **A person accepts or refuses every change**, even after an `ACCEPT`.
The evidence rule is in [`../CLAUDE.md`](../CLAUDE.md), section Evidence.
Agents start from existing ones and are trialled before being kept: [ADR 0001](../docs/adr/0001-start-from-existing-agents.md).

1. **Log** the error in a ledger kept outside this repository. A single error changes nothing.
2. **Same error twice** for one target, or once more after its case (`due`): write a test case first, and log it with `case`.
3. **Choose the place**: a script or a hook, else a file read on demand, else a line in the agent.
4. **Change little**: four changes at most, without making the file longer.
5. **Keep** only if the reserved checks rise over 3 runs, with no regression, on the same model.
6. **Log what was refused**, outside this repository too: `gate` prints the line, as JSON.
7. **Prune** every month, or when the model changes.

## Commands

```
python agents/loop.py size
python agents/loop.py due --ledger FILE
python agents/loop.py report --ledger FILE [--date YYYY-MM-DD]
python agents/loop.py run --candidate NAME [--role AGENT] --runs 3 --model MODEL --out SCORES.json [--max-budget-usd CAP --yes]
python agents/loop.py scores --skill NAME --model MODEL --out SCORES.json RUN RUN RUN [-- GRADER_ARGS]
python agents/loop.py gate --base BEFORE.json --new AFTER.json --agent AGENT_OR_SKILL_MD --base-rev REV
python agents/loop.py selftest
python agents/trials/data/bench.py make DIR
python agents/trials/data/bench.py grade DIR
python agents/trials/data/bench.py selftest
```

Exit codes of `loop.py`: 0 accepted or nothing to do, 1 refused, too long or due, 2 unusable input. `report` is 0 whatever it reports.
Without `--role`, `run` measures the generalist. Without `--yes`, it only prints the commands, the number of model runs and the total cap.
Give the full model name: an alias such as `opus` can point to another model between two measurements.

`size` reads the files tracked by git: `skills/*/agents/*.md`, the agents under `agents/` (a `.md` that opens with frontmatter, outside `candidates/`) and every `SKILL.md`.
A file that was already too long has its own ceiling in `CEILINGS`, reported at each run.
It also refuses a tracked `.jsonl` file outside `skills/`: a ledger has no place here. It only knows the extension.

`run` launches the data trial only.

## Ledger

This repository holds the tool and no data: [ADR 0002](../docs/adr/0002-record-of-errors-stays-outside.md). The ledger is a file of yours, one JSON object per line, where lines are only ever added at the end. An invented one:

```
{"date":"2026-01-05","project":"shop","target":"tone","error":"no-signature","source":"https://github.com/example/shop/pull/7"}
{"date":"2026-01-19","project":"shop","target":"tone","error":"no-signature","source":"https://github.com/example/shop/issues/12"}
{"date":"2026-01-20","project":"shop","target":"tone","error":"no-signature","case":"skills/tone/evals/evals.json: reply"}
{"date":"2026-02-02","project":"shop","target":"tone","error":"no-signature"}
```

`due` is empty after the first line, lists the error after the second, not after the third, and lists it again after the fourth, as come back after its case.

A line with `case` is a coverage, any other line an occurrence. No other key is allowed.

| key | value |
|---|---|
| `date` | a real date, `YYYY-MM-DD` |
| `project` | the repository that holds the target: lowercase letters, digits, `.`, `_`, `-`, 100 characters at most |
| `target`, `error` | lowercase words and digits joined by dashes, starting with a letter, 40 characters at most. No closed list |
| `source` | optional, occurrences only: `https://github.com/OWNER/REPO/` then `pull/N`, `issues/N` or `commit/` and the full hash |
| `case` | coverages only, the test: letters, digits, spaces and `.,:/_-`, 120 characters at most |

- **An error is a project, a target and an id.** Two projects can both have a target named `scripts`, whose errors have nothing in common, and a case in one protects nothing in the other.
- **One event counts once.** The same error with the same `source` is one occurrence, whatever the dates. Without `source`, one occurrence a day. The same coverage on the same date counts once. `report` gives the number of repeated lines.
- **A case covers what is above it.** An occurrence below the last coverage of its error, and not dated before it, came back: the error is due at once, until a new coverage is added.
- A coverage with no occurrence above it is refused, as it would cover nothing (a mistyped id).
- The whole file is read or none of it: a bad line, an empty or missing file, or a last line without an end is exit 2, with the line number. Check a copy with `due` before you add a line for good.

`report` prints Markdown: what is due first, then all the counts, with the sources as links, then the ids spelled alike for the same project and target. It names projects and links: keep it private. `--date` sets the last day of the 30-day windows (today in UTC if absent). The report does not hold `size`, which is about this repository only.

## Budget

`--yes` needs `--max-budget-usd`, the cap of one run in US dollars. It is passed to the CLI and checked again on the reported cost.
A run that fails, is stopped by the cap or costs as much as the cap is reported with its cost as not measured: it is not scored and the series stops.
A run that works but reports no cost is recorded with `cost_usd` null, never 0.
Read in the program of Claude Code 2.1.332, not tested with a real run: the cost is `total_cost_usd`, and a capped run has `is_error` true and the subtype `error_max_budget_usd`. Whether a run can spend more than its cap is unverified.

## Skills

The loop does not launch skill runs, and there is no common launcher: make them as rule 2 of [`../CLAUDE.md`](../CLAUDE.md) says, with the skill, one folder of answers per run, outside `skills/NAME/`.
Leave out a run whose launcher reported a failure: its answers are not a measure.

`scores` grades at least three folders with `skills/NAME/evals/grade.py` and writes the file `gate` reads; what follows `--` goes to the grader (`--org`, `--os`), the same for both files.
A missing answer or a grader that fails is exit 2, never a failed check.

When the two files name a skill, `gate` also requires:

- the same skill, and the same `evals.json` and `grade.py` at both measurements (`scores` records their digest). A new case is added before both.
- `skills/NAME/evals/reserved.txt`, whose checks are all in the base file.
- the judged file under `skills/NAME/`, outside `evals/`, and nothing else changed there since `REV`, untracked files included: scripts, references and the reserved list too. Update the skill's `README.md` and `RESULTS.md` after the verdict. A change that needs several files cannot be judged here.

For a `SKILL.md`, the limit is the one of `size` (500 body lines) instead of 1,500 words. The number of words may not rise in any file.

The reserved mean must rise, so a skill whose published score is already full can only be refused until a harder case exists.

## Reserved checks

`trials/data/reserved.txt` lists the reserved checks (`task:check`); all the others are visible.
For a skill the list is `skills/NAME/evals/reserved.txt` (`case:assertion text`, one per line, the whole line). No skill has one yet.
A reserved check whose result was used to change an agent becomes visible: remove it from the list and replace it.
The hidden cases are published here, so a model may have seen them: they are hidden from the workspace of a run, not secret.

## Isolation on native Windows

- **Isolated, according to the Claude Code help text (unverified, not tested here)**: one new temporary folder outside the repository per run; `--restricted` confines the file tools to that folder and ignores the settings; `--safe-mode` and `--strict-mcp-config` leave out CLAUDE.md, hooks, plugins, skills and MCP servers. The model has no shell and no web, so it cannot run its code.
- **Not isolated**: grading runs the code written by the model with your rights, your network and your environment variables. No sandbox surrounds it. That code can read the hidden cases on disk.
- The `trial-*` folders stay in the temporary folder, so a failure can be read again.
