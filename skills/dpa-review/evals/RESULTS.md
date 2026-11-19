# dpa-review — evaluation results

Method: each prompt in `evals.json` was given to one headless `claude -p` session
**with** the skill and one **without** (Claude Code 2.1.328). Each case ran in a fresh git
repository holding only the fixtures from `fixtures/`; the skill was copied into
`.claude/skills/` in the "with" arm only. Answers were graded by `grade.py` — pure regex
over the answer text, no model in the loop, so a rerun grades identically. Run 1 and run 2
both took place on 2026-11-19 with the same harness.

Limits: one run per case, variance not measured. Both arms loaded the author's
user-level Claude Code configuration (global instructions and hooks), so neither is a
bare model. The recorded answers are not published.

## Scores, run 2 (current skill, all 8 `provider-training` assertions)

| Case | With the skill | Without |
|---|---|---|
| `own-contract-fr` | 8/8 | 2/8 |
| `draft-gaps-en` | 7/7 | 1/7 |
| `provider-training` | 8/8 | 1/8 |

Total: 23/23 with the skill, 4/23 without.

## Scores, run 1 (history)

Run 1 predates the Data Privacy Framework (DPF) check. Its answers regraded with the
current 8-assertion grader:

| Case | With the skill | Without |
|---|---|---|
| `own-contract-fr` | 8/8 | 2/8 |
| `draft-gaps-en` | 7/7 | 1/7 |
| `provider-training` | 7/8 | 0/8 |

On the 7 assertions `provider-training` had at the time, run 1 scored 7/7 with and 0/7
without. The with-skill miss on the 8th assertion is the point of the change below: its
transfers row asked for the executed SCCs and a transfer impact assessment but never
mentioned the DPF.

## Skill change between runs

`SKILL.md` and `reference.md` gained a rule: when data goes to the United States, the
`transfers` row asks to check that the recipient is listed as active on the Data Privacy
Framework List (https://www.dataprivacyframework.gov/list) and, if not, which other art. 46
mechanism the contract names; it never states whether the recipient is listed. `evals.json`
and `grade.py` gained the matching assertion on `provider-training`. The with-skill row now
reads, for the US provider: "Vérifier si Nimbus AI Inc. figure comme active sur la Data
Privacy Framework List ... sinon le mécanisme nommé est les clauses contractuelles types".

## Caveats

- **The `provider-training` baseline raised the DPF point and still fails.** Its answer
  says "vérifier si Nimbus est certifié au Data Privacy Framework (transfert vers les
  États-Unis)". The assertion only looks in a `transfers` table row or in a "Questions for
  a lawyer" section, and the baseline has neither, so the grader finds nothing. This is a
  format-bound failure, not a miss by the baseline: the 1/8 understates what it found.
- **`draft-gaps-en` with the skill also names the DPF, as noise.** That contract has no
  US recipient: the hosting region is the placeholder `[REGION]`. The skill's row says "for
  any US recipient, check ...", a conditional that fits an unknown region, not a US transfer
  found in the text. No assertion covers it and it does not affect the 7/7.
- The DPF assertion is a keyword match: it proves the check is raised, not that the
  wording is right.
- One run per case and the grader was extended after run 1, so run 1 and run 2 are not a
  clean before/after; the with-skill gain on `provider-training` (7/8 to 8/8) is one
  assertion.

## What the baselines got wrong

Without the skill, each agent wrote a prose summary of 300 to 350 words in the chat
(French or English following the prompt) and put its full review in a separate file
outside the answer. The grader only reads the chat answer.

### Failures about the skill's output format

The baseline cannot pass these by construction: they check for the skill's own fixed
format, which no prompt asked an unprepared agent to produce.

- No table with one row per art. 28(3) letter (a) to (h): 0 of 3 baselines. The
  baselines group by theme ("Bloquant", "À négocier", "Housekeeping") instead.
- No fixed status vocabulary (PRESENT, WEAK, MISSING, RISK, ...): 0 rows in every
  baseline. This also makes the row-specific assertions unsatisfiable (audits row
  MISSING, sub-processors row MISSING, training row RISK, transfers row, audits row
  WEAK).
- No `Revue de DPA` header, so the French-report check fails on `own-contract-fr`.
- Placeholders in `draft-gaps-en`: the chat answer says "7 placeholders are still
  blank" without naming them, so the grader finds none of the seven. The baseline did
  not miss them: its full report file lists all seven (`[CLIENT NAME]`, `[DATE]`,
  `[number]`, `[REGION]`, `[...]`, `[AMOUNT]`, `[SIGNATORY]`). That failure is about
  where the agent put its content, not about what it found.
- Same for the sub-processor and audit gaps of `draft-gaps-en`: both are named as
  "Missing, required by law" in the chat answer, but not as table rows, so the two
  row assertions fail.

Of the 19 assertions the baselines lost in run 1, 13 are this kind (3, 5 and 5 per case) and 6 are substantive. In run 2 the baselines again lose 19 (6, 6 and 7): 14 are format-bound (the extra one is the DPF assertion, see Caveats) and 5 substantive. The run-2 `provider-training` baseline no longer writes "conforme", so the verdict assertion passes on the regex, but it still opens with "Non, pas en l'état : trois clauses ne respectent pas l'article 28", a verdict in substance that the regex does not catch.

### Substantive failures

These are the ones that matter, because the skill exists to prevent them.

- **A compliance verdict.** `own-contract-fr` opens with "Les mentions obligatoires de
  l'article 28 du RGPD sont toutes présentes" and says a clause "est conforme".
  `provider-training` answers "Non, pas en l'état" and lists two clauses under
  "Non conformes à l'art. 28". These are legal conclusions; the skill reports what the
  text contains, omits or leaves weak, and leaves the conclusion to a lawyer. The grader
  caught the words "conforme" and "conformes". `provider-training` also concludes that
  the provider "devient responsable de traitement (art. 28(10))" as fact, where the
  skill turns it into a question.
- **HDS concluded, not asked.** `own-contract-fr` raises HDS, but as "Bloquant" and
  "impose un hébergeur certifié HDS (art. L.1111-8)". The skill's rule is that HDS stays
  a question for a lawyer. The baseline's closing line does send the HDS clause to a
  lawyer, but the question is not framed as one, so the assertion fails.
- **No numbered questions for a lawyer** in any baseline. Each ends with a one-line
  "not legal advice, have it checked" instead, which is a disclaimer, not the list of
  precise questions the skill produces.
- **The chat answers carry conclusions, not evidence.** Each baseline put its detail in
  a file; the chat answers quote almost no clause text and give no line numbers, where
  the with-skill tables carry both for every row.

### What the baselines did well

The baselines were not careless readers; most of their findings are real.

- All three found the main problem of their contract: the missing annexes and the HDS
  question (`own-contract-fr`), the absent audit and sub-processor clauses
  (`draft-gaps-en`), and the default training clause (`provider-training`, spotted first
  and well explained, with the advice to switch the opt-out on before sending data).
- `draft-gaps-en` noticed points outside art. 28(3): the UK entity ("Ltd") and UK GDPR,
  the missing governing law and precedence clause, the missing provider signature line.
- `provider-training` suggested checking the provider's Data Privacy Framework
  certification, which the run-1 with-skill answer did not (the run-2 one does).
- All three said what they had not read and added a not-legal-advice line.
- The chat answers are shorter and quicker to read: 300 to 350 words against a 25-row
  table. Whether a reader wants the table is the trade-off the skill makes on purpose.

### One side effect of the configuration

The `own-contract-fr` baseline wrote its full report in English despite the French
prompt (the author's global instructions require English documents); only its chat
summary is French. It is counted under the missing `Revue de DPA` header, not as a
separate failure.

## Reproducing

```bash
# produce one answer file per case, however your agent runs them
python3 grade.py <run-dir>
```

Exit code 0 means every assertion passed.
