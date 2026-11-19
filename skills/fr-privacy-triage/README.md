# fr-privacy-triage

Triage for French data-protection questions (CNIL, RGPD / GDPR, HDS, AIPD / DPIA, consent,
retention, processors and DPAs, picking an LLM or a host, a new feature or data flow) that
never gives a legal answer. Each point comes back as one of three classes:

- **SETTLED**: a professional already answered it in writing for this project, and the
  project's decision log records the answer, the role, the date and the source document.
  If the facts changed since, the point is not settled.
- **OFFICIAL**: an official page (cnil.fr, legifrance.gouv.fr, esante.gouv.fr,
  edpb.europa.eu, eur-lex.europa.eu) says it, cited with URL and access date, and labelled
  as not validated for this project.
- **OPEN**: it needs a lawyer or DPO. It is filed in the project's question list, with why it
  matters and what it blocks, once.

It is project-agnostic: the decision log and the question list are two Markdown files in
the project, created from a template on first use.

```
| Point | Classification | Reference |
|---|---|---|
| Retention of the audio after transcription | SETTLED | decision log "Audio retention", 2026-03-12 |
| What the CNIL lists as health data | OFFICIAL | https://www.cnil.fr/fr/<page>, accessed 2026-11-19 (official source, not validated for this project) |
| Whether a DPIA is required for the voice-summary feature | OPEN | lawyer-questions: Is a DPIA required for the voice-summary feature? |
```

## Usage

```
bash scripts/fr-privacy-triage.sh init
bash scripts/fr-privacy-triage.sh search retention conservation
bash scripts/fr-privacy-triage.sh ask --question "..." --why "..." --blocks "..." [--dry-run]
bash scripts/fr-privacy-triage.sh drop --question "..." [--dry-run]
bash scripts/fr-privacy-triage.sh log --question "..." --answer "..." --conditions "..." \
  --validated-by "DPO" --date 2026-03-12 --source "..." [--dry-run]
printf 'point\tOPEN\tlawyer-questions: ...\n' | bash scripts/fr-privacy-triage.sh table
```

Defaults: `docs/legal-decisions.md` and `docs/lawyer-questions.md` under the git root;
`--root`, `--log` and `--questions` override them. Needs `bash` and `awk`. `ask` refuses an
exact duplicate (`duplicate:`); otherwise it files the question and lists up to three
listed questions that share the most words with it (`candidate:`). Whether one is the same
question reworded (synonyms included) is the agent's call, by meaning; if it is, `drop`
removes the item just filed. The official-page
lookup is done by the agent with its web tools. [`sources.json`](sources.json) lists the official pages the
skill relies on, each with the excerpt it rests on, so a scheduled job can detect a change. Commands, output lines, the dedup rule and
failure messages: [`reference.md`](reference.md).

## Evaluation

Run 2 on 2026-11-19, one run per case, with the skill and without. With the skill: 7/7,
7/7, 7/7, 6/6, 7/7; without: 3/7, 3/7, 3/7, 4/6, 4/7. Run 1 (earlier skill: 6/7, 7/7, 7/7,
6/6, 7/7 with; 3/7, 2/7, 3/7, 3/6, 4/7 without) failed one assertion because the CNIL pages
returned HTTP 503. The fallback procedure and the stable official URL table were added after
it, and the grader's table rule and DPIA-verdict regex also changed between gradings. Both
arms loaded the author's user-level configuration in both runs, and variance is not
measured. See [`evals/RESULTS.md`](evals/RESULTS.md).
