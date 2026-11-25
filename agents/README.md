# Agent trials and improvement loop

The scripts measure. **A person accepts or refuses every change**, even after an `ACCEPT`.
The evidence rule is in [`../CLAUDE.md`](../CLAUDE.md), section Evidence.
Agents start from existing ones and are trialled before being kept: [ADR 0001](../docs/adr/0001-start-from-existing-agents.md).

1. **Log** the failure in `failures.md`. A single error changes nothing.
2. **Same error twice** for one agent: write a test case first, and fill in the `case` column.
3. **Choose the place**: a script or a hook, else a file read on demand, else a line in the agent.
4. **Change little**: four changes at most, without making the file longer.
5. **Keep** only if the reserved checks rise over 3 runs, with no regression, on the same model.
6. **Log what was refused** in `rejected.md`: `gate` prints the row to paste.
7. **Prune** every month, or when the model changes.

## Commands

```
python agents/loop.py size
python agents/loop.py due
python agents/loop.py run --candidate NAME [--role AGENT] --runs 3 --model MODEL --out SCORES.json [--yes]
python agents/loop.py gate --base BEFORE.json --new AFTER.json --agent AGENT --base-rev REV
python agents/loop.py selftest
python agents/trials/data/bench.py make DIR
python agents/trials/data/bench.py grade DIR
python agents/trials/data/bench.py selftest
```

Exit codes of `loop.py`: 0 accepted or nothing to do, 1 refused, too long or case missing, 2 unusable input.
Without `--role`, `run` measures the generalist. Without `--yes`, it only prints the commands and the number of model runs.
Give the full model name: an alias such as `opus` can point to another model between two measurements.

`size` reads the files tracked by git: `skills/*/agents/*.md`, the agents under `agents/` (a `.md` that opens with frontmatter, outside `candidates/`) and every `SKILL.md`.
A file that was already too long has its own ceiling in `CEILINGS`, reported at each run.

`run` and `gate` use the data trial and its `reserved.txt` only. The evals of the skills (`skills/*/evals/`) are not connected to them.

## Reserved checks

`trials/data/reserved.txt` lists the reserved checks (`task:check`); all the others are visible.
A reserved check whose result was used to change an agent becomes visible: remove it from the list and replace it.
The hidden cases are published here, so a model may have seen them: they are hidden from the workspace of a run, not secret.

## Isolation on native Windows

- **Isolated, according to the Claude Code help text (unverified, not tested here)**: one new temporary folder outside the repository per run; `--restricted` confines the file tools to that folder and ignores the settings; `--safe-mode` and `--strict-mcp-config` leave out CLAUDE.md, hooks, plugins, skills and MCP servers. The model has no shell and no web, so it cannot run its code.
- **Not isolated**: grading runs the code written by the model with your rights, your network and your environment variables. No sandbox surrounds it. That code can read the hidden cases on disk.
- The `trial-*` folders stay in the temporary folder, so a failure can be read again. A run that breaks down is not scored and stops the series.
