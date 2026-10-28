# dead-code-audit

Find dead code in any JavaScript/TypeScript repo with [Knip](https://knip.dev), zero-install,
and know what is actually safe to remove. The script categorizes Knip's findings and scores
them; the skill adds the guardrails that keep a false positive from getting real code deleted.

## Usage

```bash
bash skills/dead-code-audit/scripts/dead-code-audit.sh [<dir>] [--runner npx|pnpm|yarn]
```

- `<dir>` — repo root to audit (default: current directory).
- `--runner` — override the runner; by default it is read from the lockfile.

Needs Node (for `npx` / `pnpm dlx` / `yarn dlx`) and `jq`. Knip is fetched on demand, so
nothing is added to the repo. The script is read-only and deletes nothing.

## Sample output

```
Dead-code audit · web · 2026-10-28 · Knip · no Knip config, using Knip defaults

Unused files (2)
- src/legacy/old-widget.tsx
- src/utils/unused-helpers.ts

Unused exports (1)
- src/api/client.ts:42	buildLegacyUrl

Unused exported types (1)
- src/types/models.ts:88	DeprecatedPayload

Unused dependencies (1)
- moment

Unlisted / undeclared dependencies (1)
- date-fns

Before/after score (candidates — verify against the guardrails before removing)
- removable lines of code: 213 across 2 unused file(s)
- unused dependencies: 1
```

Every line is a **candidate**. `SKILL.md` lists the false positives Knip cannot see —
dynamic imports, Module Federation, framework entry points, config-only references, public
API re-exports — and the skill rules each out before calling anything safe to remove.

Category meanings and the score definition: [reference.md](reference.md).

## Evaluation

Three deterministic cases run against a committed, self-contained fixture
(`evals/fixtures/sample-ts-project/`) with planted dead code and two live false-positive
traps, graded by regex. With the skill they score 7/7, 4/4 and 4/4; the without-skill
baseline is not measured yet. The run also exposed and fixed a config-detection defect in
the script. Method, scores and reproduction: [`evals/RESULTS.md`](evals/RESULTS.md).
