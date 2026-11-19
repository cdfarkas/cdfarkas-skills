# French data-protection triage — full reference

## Classifications

| Classification | Means | Reference column |
|---|---|---|
| `SETTLED` | a complete decision-log entry covers the point and its Conditions match the current facts | entry title and its `YYYY-MM-DD` date |
| `OFFICIAL` | an official page states it; nothing is inferred from it to the project | `https://` URL on an official domain and the access date; the script appends `(official source, not validated for this project)` |
| `OPEN` | needs the project's facts qualified by a lawyer or DPO | the question as filed in the question list |

Official domains accepted by `table`: `cnil.fr`, `legifrance.gouv.fr`, `esante.gouv.fr`,
`edpb.europa.eu`, `eur-lex.europa.eu`, and their subdomains.

There is no fourth class. A point that is "probably fine" is OPEN.

## Stable official URLs

Fallbacks for recurring topics when the page found by search fails. Each one loaded with
the expected content on 2026-11-19; that is a check, not an access date to cite: cite the
date you read it.

| Topic | URL | Content |
|---|---|---|
| HDS obligation (art. L.1111-8 CSP) | https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000049577902 | version in force since 2025-07-01; II: a digital host holds a certificate of conformity |
| HDS scope and short-period exception (art. R.1111-8-8 CSP) | https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000036656709 | I: defines the hosting activity; "Toutefois": data entrusted "pour une courte période" is not hosting |
| CNIL list of processing requiring a DPIA (délibération 2018-327) | https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000037559521 | the 14-type list, stated as non-exhaustive |
| Processor obligations, art. 28 clauses (CNIL guide du sous-traitant, 2017) | https://www.cnil.fr/sites/default/files/atoms/files/rgpd-guide_sous-traitant-cnil.pdf | PDF; includes sample processing clauses |
| Security measures (CNIL guide sécurité, 2024) | https://www.cnil.fr/sites/default/files/2024-03/cnil_guide_securite_personnelle_2024.pdf | PDF |

Légifrance answers `curl` with 403 but loads through a web-fetch tool; the CNIL PDFs load
with `curl`. Not listed because they failed that day: the GDPR text on cnil.fr (chapter
pages, HTTP 503), the esante.gouv.fr HDS page (empty body), EUR-Lex (refuses automated reads).

Each page, with the excerpt relied on and its read status: [`sources.json`](sources.json).

## Files

Both paths are relative to the project root (`--root`, default the git top level, else the
current directory) unless absolute.

| File | Default | Override | Written by |
|---|---|---|---|
| decision log | `docs/legal-decisions.md` | `--log PATH` | `init`, `log` |
| question list | `docs/lawyer-questions.md` | `--questions PATH` | `init`, `ask` |

A decision-log entry is a `### <title>` heading followed by these bullet fields:

```
### <short title>
- Question:
- Answer:
- Conditions: (facts the answer depends on; if any changes, the entry no longer applies)
- Validated by: (role, not name)
- Date: YYYY-MM-DD
- Source document: (path or reference of the written answer)
```

An indented line continues the field above it. Headings inside a fenced block (the
template) are ignored.

## Commands and output

| Command | stdout |
|---|---|
| `init` | `created: <path>` or `exists: <path>`, one per file; `dry-run: would create <path>` |
| `search <kw>...` | one block per matching entry (below), or `no entry matches: <kw>...` |
| `ask --question --why --blocks` | `appended: <path>` then the item, or `duplicate: already listed at <path>:<line>: <line text>`; `dry-run: would append ...` then the item |
| `log --question --answer --conditions --validated-by --date --source` | `logged: <path>` then the entry; `dry-run: would append ...` then the entry |
| `table` | the markdown table `Point | Classification | Reference` |

A `search` block:

```
entry: <title>
  question: ...
  answer: ...
  conditions: ...
  validated by: ...
  date: YYYY-MM-DD
  source document: ...
  status: complete
```

`status: incomplete (missing: <fields>) - not citable as SETTLED` when a field is empty or
the date is not `YYYY-MM-DD`.

Keywords match whole words by prefix, case- and accent-insensitive: `conserv` matches
"Conservation", `donnees` matches "données". An entry matches when any keyword does.

## Deduplication

`ask` compares the new question with every line of the question list, after stripping a
list marker (`-`, `*`, `1.`, `#`) and a leading `Q:`, lowercasing, folding French accents
and dropping punctuation. "Les données vocales sont-elles des données de santé ?" and "les
donnees VOCALES sont elles des donnees de sante" are the same question. A reworded
question is not caught; neither is one wrapped over several lines in a hand-written list.

New items go at the end of the `## Added later` section (created at the end of the file if
missing); no other section is edited. Each item:

```
- Q: <question>
  - Why it matters: <risk or obligation>
  - Blocks: <decision or step>
  - Added: YYYY-MM-DD
```

## Failures

Exit 2 on usage errors, 1 on the rest; the cause is the last stderr line.

| Message | Cause |
|---|---|
| `no decision log at <path>; run init first` | `search` before `init`, or a wrong `--log` |
| `search: give at least one keyword` | no keyword |
| `ask: --question, --why and --blocks are all required` | a missing field |
| `log: refused, a validated answer needs --<field>...` | a missing field |
| `log: refused, --date must be YYYY-MM-DD (got '<value>')` | a date in another format |
| `table: line N: <reason>` | a row with an unknown classification, an OFFICIAL row without an official URL or access date, a SETTLED row without a date, an OPEN row without a reference; nothing is printed on stdout |
| `table: no rows on stdin` | empty input |

## Why the script and not prose

The three classes are only worth something if they are applied the same way every time.
An agent left to itself fills the gap between "the CNIL says" and "so you may" with an
inference, and quietly duplicates questions across sessions. The script holds the parts
two agents would do differently: what an entry needs to be citable, what a question
duplicate is, what an OFFICIAL row must carry. Reading official pages and judging whether
Conditions still hold stay with the agent, and the table makes those judgements visible.
