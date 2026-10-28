---
name: dead-code-audit
description: >
  Audit a JavaScript/TypeScript repo for dead code with Knip, zero-install, and decide
  what is safe to remove: unused files, unused exports, unused exported types, unused
  dependencies and unlisted/undeclared dependencies, each categorized, with a before/after
  score (removable lines of code, unused-dependency count). Use when someone asks to find
  dead code, unused exports or unused dependencies, to detect unused code, run knip, or
  trouver du code mort. Every finding is a candidate: the skill flags likely false positives
  before anything is deleted. Needs Node (for npx/pnpm/yarn) and jq.
license: Apache-2.0
---

# Dead-code audit

Two steps. The script runs Knip and **categorizes** its findings deterministically — do
not re-parse the JSON by hand. You add the **judgment** Knip cannot: which findings are
false positives, and therefore what is actually safe to remove.

## Step 1 — run the script

```bash
bash <skill-dir>/scripts/dead-code-audit.sh [<dir>] [--runner npx|pnpm|yarn]
```

`<skill-dir>` is the directory holding this file. Map what the caller said to flags:

| Caller says | Flag |
|---|---|
| nothing, "this repo" | no argument — the current directory is audited |
| a path or sub-package | pass it as `<dir>` |
| "use pnpm / yarn", or detection picks the wrong one | `--runner pnpm` / `--runner yarn` |

The runner defaults to the lockfile (`pnpm-lock.yaml` -> pnpm, `yarn.lock` -> yarn, else
npx). Knip runs zero-install; if the repo has no Knip config the script says so and uses
Knip's defaults. Needs Node and `jq`. A medium repo takes 10 to 60 seconds. The script is
read-only — it deletes nothing.

## What comes back

A header line, then one section per category — unused files, unused exports, unused
exported types, unused dependencies, unlisted/undeclared dependencies — and a before/after
score: removable lines of code (summed over the unused files) and the unused-dependency
count. Category meanings and the score definition: [reference.md](reference.md).

## Step 2 — apply the guardrails, then report

Knip reasons from static imports. **Every line it prints is a candidate, not a verdict.**
Before you call anything removable, rule out the false positives Knip cannot see — do not
auto-delete, and never run a bulk removal:

- **Dynamic imports** — `import(\`./\${name}\`)`, `require(variable)`, a glob loader: the
  target is referenced at runtime, never statically. Grep the repo for the base path.
- **Module Federation** — anything under `exposes`, a `remoteEntry`, or `shared` in the
  bundler config is consumed by another app, not this build. Treat as used.
- **Framework entry points** — route files, `pages/`/`app/` conventions, `*.config.*`,
  service workers, migration and seed scripts: run by the framework or a tool, not imported.
- **Referenced only in config** — a file named in `tsconfig`, a test matcher, a CI script
  or a package `"bin"`/`"exports"` map is used even with no import.
- **Public API re-exports** — a package `index` re-exporting for external consumers looks
  unused inside the repo; check the package manifest's `exports` field and who installs it.

For a candidate you cannot rule out, open the file at the reported line before deciding.
Then report the categorized findings and the before/after score, and state plainly which
candidates survived the guardrails (safe to remove) versus which need a human to confirm.
The score is the ceiling — what Knip sees — not a promise that every line is dead.

## Failures

The script exits non-zero with the cause on its **last** stderr line: `jq` missing, the
target is not a directory, Knip failed to run (Node absent, or the runner could not fetch
it), or Knip produced no parseable JSON. Relay that line and stop — never invent a report
or produce one from a partial run. A dead-code list that is wrong gets real code deleted.
