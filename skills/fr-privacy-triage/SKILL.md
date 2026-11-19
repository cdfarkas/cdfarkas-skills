---
name: fr-privacy-triage
description: >
  Triage a French data-protection question for any project without ever giving a legal
  answer: each point is SETTLED (a professional's validated answer in the project's decision
  log), OFFICIAL (an official page, cited with URL and date) or OPEN (filed, deduplicated, in
  the project's question list for a lawyer or DPO). Use for CNIL, RGPD / GDPR, HDS
  (hébergement de données de santé), données de santé / health data, AIPD / DPIA,
  consentement / consent, durée de conservation / retention, sous-traitant / processor, DPA,
  transfers outside the EU, choosing an LLM or hosting provider (hébergeur), or reviewing a new
  feature or data flow (nouvelle fonctionnalité, flux de données) that touches personal or
  health data. Needs bash and awk.
license: Apache-2.0
---

# French data-protection triage

This skill never gives legal advice. It sorts what the person asked into points a
professional has already validated, points an official page states, and points only a
lawyer or DPO can answer, and it files the last kind so they get asked.

## Hard rules

- Never present a point as SETTLED unless the script's `search` printed its entry with
  `status: complete` and the current facts match the entry's Conditions.
- Never write "compliant", "conforme", "legal", "you are fine", "pas de problème", or any
  verdict that the project may or may not do something. Say what is settled, what a page
  says, and what is open.
- Official means cnil.fr, legifrance.gouv.fr, esante.gouv.fr, edpb.europa.eu,
  eur-lex.europa.eu, read in this session. Vendor pages, blogs, forums and your own memory
  are not sources; they can suggest a question, never answer one.
- Answer in the language the person used. The answer always ends with the table from step 5.

## The script

```bash
bash <skill-dir>/scripts/fr-privacy-triage.sh <command> [--root DIR] [--log PATH] [--questions PATH] [--dry-run]
```

`<skill-dir>` is the directory holding this file. The project root defaults to the git top
level; the decision log to `<root>/docs/legal-decisions.md` and the question list to
`<root>/docs/lawyer-questions.md`. Pass `--log` / `--questions` when the person names other
files, and keep passing them on every call.

## Procedure

1. **Split** the question into atomic points: one fact, one obligation or one choice each
   ("is this health data", "does the provider need a DPA", "is a DPIA required", "where is it
   stored", "how long is it kept"). For a new feature or data flow, the points are the
   checklist lines below.
2. **SETTLED?** Run `init` (it only creates what is missing), then `search <keyword>...`
   with French and English keywords for each point (`conservation retention`,
   `hebergeur hosting`). For each entry printed:
   - `status: incomplete` → not citable; treat the point as OPEN.
   - compare every Conditions fact with the current situation (provider, data, people,
     storage place, channel, purpose). If any differs, say which one, cite the entry and its
     date as the reason, and treat the point as OPEN.
   - otherwise the point is SETTLED: give the entry's answer, its title and its date.
3. **OFFICIAL?** For a point not settled, look it up live on the official sites above
   (search, then fetch the page). Quote or paraphrase only what the page says, with its URL
   and the access date, labelled "official source, not validated for this project". Do not
   infer from the page to this project's facts: "the CNIL says health data requires X" is
   OFFICIAL; "so your recordings are health data" is OPEN. An OPEN point still gets an
   OFFICIAL row for the rule it rests on: its qualification stays OPEN, the rule's text is
   OFFICIAL.

   When a page returns 5xx, 404 or an empty body: retry it once; then `curl -sL <url>`; then
   the stable URLs for the topic in [reference.md](reference.md#stable-official-urls) (CNIL
   PDFs under `cnil.fr/sites/...` often load while its HTML pages fail; EUR-Lex refuses
   automated reads). Never cite a page you did not read, and say in the answer which
   official pages failed.
4. **OPEN.** Anything that needs the project's facts qualified (HDS scope, controller or
   processor roles, legal basis, whether a provider is acceptable, whether a DPIA is
   required, transfer mechanism) is never concluded. File each one:

   ```bash
   bash <skill-dir>/scripts/fr-privacy-triage.sh ask --question "<question for a lawyer/DPO>" \
     --why "<risk or obligation at stake>" --blocks "<decision or step it blocks>"
   ```

   `appended:` means it was added under `## Added later`; `duplicate: already listed at
   <file>:<line>` means it was already there: cite that line instead. One question per call.
5. **Table.** Pipe one line per point, `point<TAB>classification<TAB>reference`, into
   `table`, and end the answer with its output, unchanged:
   - SETTLED: the entry title and its date, e.g. `decision log "Audio retention", 2026-03-12`
   - OFFICIAL: the URL and the access date; the script adds the "not validated" label
   - OPEN: the question as filed, e.g. `lawyer-questions: Is a DPIA required for ...?`

   A `table: line N:` error on stderr names a malformed row: fix the row, never the rule.

## Logging a validated answer

Only when the person supplies a professional's answer with the role (not the name), the
date and the source document, record it with `log --question --answer --conditions
--validated-by --date --source`. The script refuses an entry with a missing field or a
date not in `YYYY-MM-DD`. Never log your own reading, an official page, or "the lawyer
said it's fine" without a date and a document. Writes take `--dry-run` to preview.

## Checklist: new feature or data flow

Answer each line from the code or the spec; a line you cannot answer from them, or that
needs qualification, is an OPEN point.

- What data: fields, free text, audio, images, files. Could any of it be health data, or
  data about a minor?
- Whose data: users, minors, their parents, professionals, third parties named in free text.
- Minimisation: can it work with less (no name, place, date of birth, diagnosis)?
- Where processed and where stored: device, region, provider; transient or persisted; logs
  and backups included.
- Provider: is there a signed DPA (article 28 GDPR terms); does it train on the data; is it
  HDS-certified where health data is hosted for others.
- Transfers outside the EU, including support access and sub-processors.
- Retention and deletion: how long, who deletes, how deletion is checked on the provider side.
- Recipients: who sees the output, through which channel, with which access control.
- Documents: does it change the processor contract, the information notice, the records of
  processing, or an existing DPIA, or trigger a new one?

Script commands, output lines and failure messages: [reference.md](reference.md).
