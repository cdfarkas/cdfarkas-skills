# dpa-review

A review of a data processing agreement (GDPR art. 28), in French or English, whichever side
you are on: the DPA you send your clients, or a provider's DPA you are asked to accept. It
lists what is present, weak or missing against art. 28, the risk points beyond the minimum,
the placeholders still in brackets, and the questions to take to a lawyer. It never says the
contract is compliant.

## Usage

In an agent, ask in plain words: "relis mon contrat de sous-traitance avant que je l'envoie",
"can we sign this vendor DPA?", "check this data processing addendum".

The script behind it, step by step:

```bash
bash scripts/dpa-review.sh extract <contract>        # plain text, .md .txt .docx .pdf
bash scripts/dpa-review.sh locate <contract>         # candidate lines per item
bash scripts/dpa-review.sh placeholders <contract>   # every [bracket] left
bash scripts/dpa-review.sh render <verdict> --contract <contract> [--lang fr]
```

The agent writes the verdict file between `locate` and `render`: one line per item with its
status, evidence and fix, and at least one question for a lawyer. `render` refuses an
incomplete verdict instead of printing a partial table. Needs `bash` and `awk`; `unzip` for
`.docx`, `pdftotext` (poppler) for `.pdf`. Items, vocabulary, verdict format and sources:
[`reference.md`](reference.md).

## Sample output

`render` on the `evals/fixtures/dpa-draft-gaps.md` fixture, abridged:

```
DPA review · dpa-draft-gaps.md · 2026-11-19 · 18 mandatory: 9 present, 4 weak, 5 missing · 3 risk points

| Item | Status | Evidence | What to fix or ask |
|---|---|---|---|
| 28(3)(a) Documented instructions | PRESENT | §4.1 L25 "only on documented instructions" | - |
| 28(3)(d) Engaging sub-processors | MISSING | - | Add a sub-processing clause |
| 28(3)(h) Audits and inspections | MISSING | - | Add audits including inspections |
| breach-delay Breach notification delay | RISK | §4.5 L31 "[number] hours" | Fill the number of hours |
…

## Placeholders (7)
- L3: [CLIENT NAME]
- L31: [number]
…

## Questions for a lawyer
1. Does the liability cap need to carve out data protection claims?

Not a legal opinion: this lists what the contract contains, lacks or leaves weak against GDPR art. 28. A lawyer decides.
```

## What it does not do

It does not assess standard contractual clauses or a transfer impact assessment, national
law beyond flagging the French HDS question, or the main services agreement. The candidate
locator is a regex over lines; the agent decides every status by reading the contract.

## Sources

[`sources.json`](sources.json) lists every official page the skill relies on, with an exact quote
and a read / unread status, so a scheduled job can detect when a rule changes.

## Evaluation

One run per case, with and without the skill, graded by `evals/grade.py` (regex only):

| Case | With the skill | Without |
|---|---|---|
| `own-contract-fr` | 8/8 | 2/8 |
| `draft-gaps-en` | 7/7 | 1/7 |
| `provider-training` | 7/7 | 0/7 |

Most of the gap is the skill's fixed table, which a baseline cannot reproduce. The
substantive gap is that baselines give a verdict ("conforme", "non conformes", "pas en
l'état"), state HDS as a requirement and leave no numbered questions for a lawyer. They
also found real problems, such as the missing annexes and the unlimited training clause.
Details, limits (one run, author's configuration loaded in both arms) in
[`evals/RESULTS.md`](evals/RESULTS.md).
