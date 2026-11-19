# fr-privacy-triage — evaluation results

Method: each of the five prompts in `evals.json` was run twice on 2026-11-19, **with**
the skill and **without** it, each in its own headless `claude -p` session (Claude Code
2.1.328, its default model). A runner script copies the case's fixture from `fixtures/`
into a fresh directory, runs `git init` and a first commit, and, for the with-skill arm,
copies the skill (minus `evals/`) into `.claude/skills/`. It then sends the prompt with
`Bash Read Write Edit Glob Grep WebFetch WebSearch Skill` allowed, saves the answer as
`<case>.md` and the project's `docs/lawyer-questions.md`, if any, as
`<case>.questions.md`. `grade.py` grades the pair by regex, no model in the loop, so a
rerun grades identically. The raw answers are not published: they carry local paths.

Two complete runs exist, both on 2026-11-19. **Run 2 is the headline**; run 1 is kept as
history.

Four caveats.

- **The skill changed between the runs.** After run 1, `SKILL.md` step 3 gained a fallback
  for a failing official page (retry, `curl`, then the stable URLs) and `reference.md`
  gained a table of stable official URLs. Run 2 measures the changed skill; the run 1
  with-skill scores measure the earlier one.
- **The grader changed between gradings.** `final_table()` first required the
  classification table to be the very last lines of the answer; it now takes the last
  table with a `Point | Classification | Reference` header and tolerates trailing prose.
  The DPIA-verdict regex was also tightened. Both runs are regraded here with the current
  grader, identically in both arms.
- **Both arms loaded the author's user-level Claude Code configuration** (global
  instructions and hooks), in both runs. That is why answers in both arms tend to end with
  an "I did not verify X" note. The configuration is the same in both arms, but it is not
  a clean-room run.
- **One run per case per run number; variance is not measured.** A model session is not
  deterministic, so a one-point difference between runs is not a finding.

## Scores

Run 2 (current skill, current grader):

| Case | With the skill | Without |
|---|---|---|
| `llm-api-child-reports` | 7/7 | 3/7 |
| `dpia-feature` | 7/7 | 3/7 |
| `voice-notes-local-pc` | 7/7 | 3/7 |
| `settled-by-log` | 6/6 | 4/6 |
| `conditions-differ` | 7/7 | 4/7 |

Total: 34/34 with, 17/34 without.

Run 1 (earlier skill, regraded with the current grader):

| Case | With the skill | Without |
|---|---|---|
| `llm-api-child-reports` | 6/7 | 3/7 |
| `dpia-feature` | 7/7 | 2/7 |
| `voice-notes-local-pc` | 7/7 | 3/7 |
| `settled-by-log` | 6/6 | 3/6 |
| `conditions-differ` | 7/7 | 4/7 |

Total: 33/34 with, 15/34 without. Run 1 was first graded with the older table rule at
6/7, 7/7, 4/7, 4/6, 7/7 with the skill and 3/7, 3/7, 3/7, 3/6, 4/7 without. The table-rule
change moved only the two with-skill cases whose answers end with a note after the table.
The DPIA-verdict regex missed the run 1 baseline `dpia-feature` answer ("Yes, very
likely"), which then scored 3/7 and now scores 2/7; it now also catches "yes / oui, (very /
très) likely / probablement" at the start of a line, "you do / don't / will need a DPIA",
"vous devez réaliser une AIPD", "pas besoin d'AIPD" and "une AIPD est (très probablement)
obligatoire", and still skips questions and "whether / si une AIPD est ..." mentions.

The with-skill gain on `llm-api-child-reports` follows the skill change (below). The
baseline moved on two cases (`dpia-feature` 2/7 to 3/7, `settled-by-log` 3/6 to 4/6) for
reasons that are not the skill, since the baseline does not load it.

## Run 2 findings

**`llm-api-child-reports` now has OFFICIAL rows.** Four, each with a URL and
`accessed 2026-11-19`:

- CNIL guide du sous-traitant (PDF, art. 28 contract).
- Legifrance art. L1111-8 CSP (HDS certificate).
- Legifrance art. R1111-8-8 CSP (short-period exception).
- Legifrance JORF text of deliberation 2018-327 (CNIL DPIA list).

All four are exactly the URLs of the stable table in `reference.md`, not invented. The
answer quotes passages that match those pages (the "titulaire d'un certificat de
conformite" wording of L1111-8, the "courte periode" exception of R1111-8-8, the
"accompagnement social ou medico-social" entry of the DPIA list), which indicates it read
them. I did not confirm the quotes against the pages: `curl` returned HTTP 200 for the CNIL
PDF (about 597 kB) but HTTP 403 for the three Legifrance pages (a bot block, 5 kB body), so
only the PDF was independently confirmed readable. The cnil.fr GDPR article pages still
returned 503 in this run; the answer says so and cites none of them, which is the
specified behaviour.

**`dpia-feature` baseline: the failure is right, the grader's evidence is wrong.** The
assertion "no conclusion that a DPIA is or is not required" fails correctly, because the
baseline answer opens with "**Yes, almost certainly.**", a real verdict. But the evidence
the grader prints is the sentence "Under Art. 35 a DPIA is required when processing is
'likely to result in a high risk'", which is a statement of the rule, not a verdict. The
failing verdict is the opening line; the score is right and the evidence line points at the
wrong sentence.

**`settled-by-log` baseline went from 3/6 to 4/6 because of the entry title.** The
assertion "names the entry it relies on" looks for "Audio retention after transcription".
Run 1 gave the 30 days and the file path but not the title; run 2 writes that it is logged
in `docs/legal-decisions.md` under "Audio retention after transcription". The model varied
its wording between runs with no skill involved, which is the single-run noise caveat, not
an improvement. The other two baseline failures there (no table, no SETTLED row citing the
date) are unchanged.

## What the baselines got wrong

The five run 1 baseline answers were read in full; run 2 scores are the same on three
cases and one point higher on two. All were competent prose and share the same gaps:

- **No classification table.** None of the five has a SETTLED / OFFICIAL / OPEN table, so
  the table assertion fails in every case, and the OPEN, OFFICIAL and SETTLED assertions
  with it.
- **No question filed.** No baseline created or extended `docs/lawyer-questions.md`
  (`settled-by-log` and `conditions-differ` left the fixture's file untouched;
  `conditions-differ` offered to write the question "if you want"). The open points stay
  in the chat answer, where nothing deduplicates them or hands them to a lawyer.
- **No official source cited.** Without the skill, no answer carries a CNIL, Légifrance or
  EDPB URL with a date. `dpia-feature` names the EDPB guidelines (WP248) and recital 91
  from memory and says it did not check the CNIL list.
- **Verdicts.** The grader's "no compliant verdict" assertion passed for all five, so the
  baselines did avoid a literal "conforme". They still lean on legal conclusions:
  `dpia-feature` opens with "Yes, very likely" and `llm-api-child-reports` states that a
  DPIA is "very probably mandatory" and that the HDS question is "debatable". The
  `dpia-feature` conclusion is the one the skill is built to withhold; the first DPIA-verdict
  regex did not match its wording and scored it as a pass, the tightened one fails it.
- **Settled answer not tied to its entry.** `settled-by-log` gave the right 30 days and
  the right date, and listed the entry's conditions, but did not name the entry by its
  title.

What the baselines did well: they read the fixture, they flagged what they had not
verified, and `conditions-differ` correctly said the 2026-03-12 entry no longer applies.
The skill's gain is structure and a filed question list, not better legal knowledge.

## Remaining failures of the skill

None in run 2: every with-skill assertion passes. In run 1 one assertion failed, and it
was a real failure of the run, not a grader artefact: **`llm-api-child-reports`, "an
OFFICIAL row, each with an official URL and a date"**. The two CNIL pages returned HTTP 503
twice each and the HDS page loaded empty, so the session had no official page to cite; the
skill did not cite what it had not read, and the assertion failed. That failure produced
the fallback procedure and the stable URL table, and run 2 passes it. One passing run does
not show the fallback is robust: a day when the official sites refuse the fetch again would
leave only OPEN rows.

Not measured: robustness over repeated runs. Each cell is one run.

## Changed since the runs: reworded questions

After run 2, `ask` gained a ranking of the listed questions closest to the one it files
(`candidate:` lines, advisory, never blocking) and the skill a `drop` command: the agent
judges by meaning whether a candidate is the same question and, if so, drops the item it
just filed and cites the candidate (rule in `reference.md`, "Deduplication"). Exact
duplicates are still refused as before. No case was re-run.

- No prompt files a question that is already listed: in `evals.json` the `no-docs` and
  `feature-spec` cases start with no question list, and the `with-log` fixture's list has an
  empty `## Added later`. So no case targets this change and none measures it.
- The scores above should hold: the question-list assertions need one item (or one about
  the DPIA, or the cloud provider) and `ask` still writes it. They would drop only if the
  agent wrongly judged a needed question a duplicate of another one filed in the same run
  and dropped it. Not verified: the run 2 answers and question lists are not published and
  were not re-read for this change.

## Reproducing

```bash
# one answer file and one .questions.md per case, however your agent runs them
python3 grade.py <run-dir>
```

Exit code 0 means every assertion passed.
