# ADR 0002 — The tool is public, the record of errors stays outside this repository

## Status

Accepted (2026-11-25).

## Context

The improvement loop changes something only when the same error happens twice, so it needs a record of
errors. This repository is public. An error can come from work that is not, and what was recorded here
would stay in the history for good. The log files that were here stayed empty.

Alternatives considered:

- lines in the commit messages of this repository: public, not editable once merged, and limited to the
  errors that a commit of this repository fixes;
- a log file in this repository: the same exposure, and one repository only;
- a hook that collects facts at the end of each session: it runs in every project, needs a filter for
  what may be kept, and the reason of an error is in the fix or the correction, not in such facts.

## Decision

This repository holds the tool, its tests and invented examples. The record is a file kept outside, with
ids and links only and no free text. `agents/loop.py` reads the file it is given with `--ledger`, has no
default path and writes nothing. `gate` prints its refusals, and the log of refusals stays outside too.

The entries are written by the person or the agent of the session in which the error was corrected.

## Consequences

- No error of another project can appear here, and one ledger covers several projects.
- A forgotten entry is not caught.
- Nobody else can check the counts behind a change. The trial or the evaluation published with it stays
  the evidence.
- The wording of an id is chosen by its author: the same error under two ids is not a repeat. The report
  only lists the ids spelled alike.
- One bad line makes the whole ledger unusable until it is fixed, so a writer checks the file first.
- Storing, protecting and scheduling are left to the owner of the ledger. `loop.py size` refuses a tracked
  `.jsonl` file outside `skills/`, by its name only.
