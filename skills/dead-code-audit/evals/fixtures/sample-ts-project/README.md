# sample-ts-project — dead-code-audit fixture

A deliberately tiny TypeScript project with known, planted dead code, used by the
`dead-code-audit` eval (`../../evals.json`, graded by `../../grade.py`). `knip.json`
declares `entry` and `project` explicitly so Knip's file-level verdict is stable across
versions; the before/after numbers are therefore fixed and the eval can assert them.

Not meant to install or build — nothing imports `left-pad`, and `plugin-a` is loaded
through a dynamic specifier on purpose.

## What is planted, and what Knip should say

| File / entry | Live? | Knip verdict | Why |
|---|---|---|---|
| `src/index.ts` | live | used (entry) | the declared entry point |
| `src/used-helper.ts` | live | used | imported by `index.ts` |
| `src/api.ts` | live | `buildLegacyUrl` is an **unused export** | the file is reached, but that one export is imported nowhere |
| `src/types.ts` | live | `DeprecatedPayload` is an **unused exported type** | reached, but that type is imported nowhere |
| `src/unused-widget.ts` | **dead** | **unused file** | nothing imports it — the one genuinely removable file |
| `src/plugins/plugin-a.ts` | live | **unused file (false positive)** | loaded only via `import(\`./plugins/${name}.js\`)`, a non-static specifier Knip cannot resolve |
| `src/registry.ts` | live | **unused file (false positive)** | referenced only as a string in `app.config.json`, which Knip does not parse |
| `left-pad` (dependency) | — | **unused dependency** | in `package.json`, imported nowhere |

So the script reports 3 unused files (one real, two live traps), 1 unused export, 1
unused exported type, 1 unused dependency, and a removable-LOC score that sums all three
flagged files. The two traps are the false-positive story: Knip flags them, the agent's
guardrail step (SKILL.md) rules them out, and only `unused-widget.ts` is truly safe to
delete.
