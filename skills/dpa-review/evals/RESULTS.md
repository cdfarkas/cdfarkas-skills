# dpa-review — evaluation results

Method: each prompt in `evals.json` was given to one headless `claude -p` session
**with** the skill and one **without** (Claude Code 2.1.328), on 2026-11-19. Each case
ran in a fresh git repository holding only the fixtures from `fixtures/`; the skill was
copied into `.claude/skills/` in the "with" arm only. Both answers were graded by
`grade.py` — pure regex over the answer text, no model in the loop, so a rerun grades
identically.

Limits: one run per case, variance not measured. Both arms loaded the author's
user-level Claude Code configuration (global instructions and hooks), so neither is a
bare model. The recorded answers are not published.

## Scores

| Case | With the skill | Without |
|---|---|---|
| `own-contract-fr` | 8/8 | 2/8 |
| `draft-gaps-en` | 7/7 | 1/7 |
| `provider-training` | 7/7 | 0/7 |

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

Of the 19 assertions the baselines lost, 13 are this kind (3, 5 and 5 per case) and 6 are substantive.

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
  certification, which the with-skill run did not.
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
