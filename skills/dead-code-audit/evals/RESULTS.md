# dead-code-audit — evaluation results

Method: the three prompts in `evals.json` run against a **committed, self-contained
fixture** — `evals/fixtures/sample-ts-project/`, a tiny TypeScript project with a
pinned `knip.json` and known, planted dead code. The with-skill answer is the skill's
script output, graded by `grade.py` — pure regex over the text, no model in the loop,
so the fixture grades the same way every time.

The skill's script is **prompt-independent**: it prints the same categorized report
whatever the question. So the three cases are not three different outputs — they are
the one report graded on three slices (the planted findings, the before/after score,
the false-positive guardrails). The answer files are therefore identical copies of
that report.

Run on 2026-10-28 with Knip 6.43.0 on Windows Git Bash, Node 24. The script's own run
is about 2.5 s once Knip is cached by `npx` (the first run also fetches Knip).

## What the fixture plants

| Planted | Where | Category it should land in |
|---|---|---|
| A genuinely dead file | `src/unused-widget.ts` | Unused files |
| An unused export | `buildLegacyUrl` in `src/api.ts` | Unused exports |
| An unused exported type | `DeprecatedPayload` in `src/types.ts` | Unused exported types |
| An unused dependency | `left-pad` in `package.json` | Unused dependencies |
| A live dynamic-import target | `src/plugins/plugin-a.ts` | Unused files (**false positive**) |
| A live config-referenced file | `src/registry.ts`, named in `app.config.json` | Unused files (**false positive**) |

`index.ts` loads `plugin-a` through `import(\`./plugins/${name}.js\`)` — a non-static
specifier Knip cannot resolve — and `registry.ts` is referenced only as a string in
`app.config.json`. Both are live, both are flagged. That is the point: the script
reports all three as unused-file candidates, and telling the one dead file from the two
traps is the agent's documented judgment step (SKILL.md, step 2), not the script's job.

## Scores

| Case | With the skill | Without |
|---|---|---|
| `findings` | 7/7 | not measured |
| `score` | 4/4 | not measured |
| `guardrails` | 4/4 | not measured |

The with-skill column is the deterministic script output measured on the committed
fixture, graded by `grade.py` (exit 0, every assertion passing). The without-skill
column is honestly **not measured** this round: a bare-agent baseline — an agent with
no skill asked the same prompts, inventing its own report shape and re-deriving Knip's
invocation — is the obvious follow-up, but it needs an isolated agent harness that this
round did not run. Until it exists, these numbers show the skill is internally
consistent (script, fixture and grader agree), not that it beats an unaided agent.

## What the eval checks

- **`findings`** — the four planted dead items each land in their correct category with
  the right count, each category section is present, and the header does **not** claim
  "using Knip defaults" when the fixture ships a `knip.json`.
- **`score`** — the before/after numbers equal the planted amounts exactly (18 removable
  lines across 3 unused files, 1 unused dependency), the file count is consistent with
  the Unused files section, and the block frames the numbers as candidates to verify.
- **`guardrails`** — both live traps are surfaced as unused-file candidates, the report
  frames findings as candidates rather than verdicts, and the genuinely dead file sits
  in the same undifferentiated list as the traps (so the script cannot be read as having
  done the judgment).

## Defect the eval found in the skill

The fixture exposed one defect in `scripts/dead-code-audit.sh`, fixed in this commit:

The Knip-config probe was `! ls knip.json knip.jsonc knip.ts knip.js .kniprc .kniprc.json`.
`ls` exits non-zero when **any** argument is missing, so a repo that ships only
`knip.json` (the common case, and the fixture's case) made the probe fail and the header
wrongly print ` · no Knip config, using Knip defaults`. The probe now tests each
candidate with `[ -e ]` and stops at the first that exists. Without the fix, the
`findings` header assertion fails (the suffix is present); with it, the header reads
`Dead-code audit · sample-ts-project · <date> · Knip` and the case passes 7/7.

This did not show up by reading the script — only by running it on a repo that has a
`knip.json` and nothing else.

## Reproducing

```bash
# from the repo root
RUN="$(mktemp -d)"
bash skills/dead-code-audit/scripts/dead-code-audit.sh \
  skills/dead-code-audit/evals/fixtures/sample-ts-project > "$RUN/findings.md"
cp "$RUN/findings.md" "$RUN/score.md"
cp "$RUN/findings.md" "$RUN/guardrails.md"
python3 skills/dead-code-audit/evals/grade.py "$RUN"
```

Exit code 0 means every assertion passed. Needs Node (for `npx knip`) and `jq`.
