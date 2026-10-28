# dead-code-audit — reference

What the script reports, where each category comes from in Knip, and how the score is
computed. The skill's judgment rules (false positives, candidate discipline) are in
`SKILL.md`; this file is the vocabulary.

## Categories

| Section | Knip source | Meaning |
|---|---|---|
| Unused files | `.files[]` | A file no other file imports. The biggest win and the biggest false-positive risk — see the guardrails. |
| Unused exports | `.issues[].exports[]` (`file:line  name`) | An exported value nothing imports. Often safe to downgrade to a local, or drop. |
| Unused exported types | `.issues[].types[]` (`file:line  name`) | An exported `type`/`interface` nothing imports. |
| Unused dependencies | `.issues[].dependencies` + `.devDependencies` + `.optionalPeerDependencies` | A package in the manifest that nothing imports. Candidate for removal. |
| Unlisted / undeclared dependencies | `.issues[].unlisted[]` | A package imported in code but **absent** from the manifest. The opposite problem: add it, do not remove anything. |

Counts are deduplicated per category. The script emits `- (none)` for an empty category
so the report always shows every category.

## Before/after score

Two numbers, both an **upper bound** — what Knip can see statically, before the guardrails:

- **removable lines of code** — the sum of `wc -l` over every unused file that still
  exists on disk. Unused *exports* and *types* are not counted here (removing an export
  rarely removes whole lines cleanly); only whole unused files contribute.
- **unused dependencies** — the deduplicated count of the Unused dependencies category.

Report it as a ceiling, never as a guarantee: the real removable total is this minus
whatever the guardrails rescue.

## Runner and config

The runner is chosen from the lockfile (`pnpm-lock.yaml` -> `pnpm dlx`, `yarn.lock` ->
`yarn dlx`, otherwise `npx --yes`) and overridden with `--runner`. Knip runs zero-install.
If no Knip config is found (`knip.json`, `knip.jsonc`, `knip.ts`, `knip.js`, `.kniprc*`, or
a `"knip"` key in the manifest), the header appends `no Knip config, using Knip defaults`,
which cover standard `package.json` entry points and common tool configs.

## Failure lines (last stderr line, verbatim)

| Line | Cause |
|---|---|
| `jq is required but not found` | Install `jq`. |
| `not a directory: <dir>` | The `<dir>` argument is wrong. |
| `unknown runner: <r> (npx|pnpm|yarn)` | `--runner` got an unsupported value. |
| `knip failed to run via '<runner>' (is Node installed?)` | Node is absent, or the runner could not fetch Knip (offline). The line above it is Knip's own last stderr line. |
| `knip produced no parseable JSON (runner: <runner>)` | Knip ran but emitted no JSON — usually a Knip-level config error on its stderr. |

The script exits non-zero on all of these and prints nothing on stdout.
