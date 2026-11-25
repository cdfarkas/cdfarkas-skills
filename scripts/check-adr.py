#!/usr/bin/env python3
"""Check the decision records in docs/adr and that the living docs follow them.

Usage: check-adr.py [<base-ref>] | --self-test      (e.g. origin/main; none = rules 1 to 5 only)

  1. a file is named NNNN-short-title.md, numbers are unique and without gaps from 0000, and the
     first line is "# ADR NNNN — title"
  2. it has the sections Status, Context, Decision and Consequences, once each
  3. its Status section is one line: "Proposed", "Accepted (YYYY-MM-DD)." or
     "Superseded by ADR NNNN (YYYY-MM-DD)."
  4. a superseding ADR exists, is newer, is accepted or itself superseded, and cites the one it
     replaces
  5. an accepted ADR is cited in a living doc, and an ADR cited there exists and is accepted
  6. with <base-ref> (from the merge base with HEAD to the working tree): an ADR accepted on the
     base is not deleted or renamed, and only its Status section may change, to "Superseded by";
     a superseded ADR does not change at all

The template, ADR 0000, is exempt from rules 3 to 6.
Exit codes: 0 ok, 1 a rule is broken or a file cannot be read, 2 bad usage or unusable base ref.
"""
from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

ADR_DIR = "docs/adr"
TEMPLATE = "0000"
LIVING = ("CLAUDE.md", "README.md", "agents/README.md", "docs/how-these-skills-are-built.md")
SECTIONS = ("Status", "Context", "Decision", "Consequences")
NAME = re.compile(r"([0-9]{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md")
STATUS = re.compile(r"Proposed|(?:Accepted|Superseded by ADR (?P<by>[0-9]{4})) \((?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})\)\.")
CITATION = re.compile(r"\bADR[ -](\d{4})\b")


def git(*args: str) -> str:
    return subprocess.run(["git", "-c", "core.quotepath=off", *args], check=True, capture_output=True, encoding="utf-8", errors="replace").stdout


def to_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").split("\n")


def split_status(text: str) -> tuple[str, list[str]]:
    """The lines of the Status section that are not blank, joined, and the lines outside it."""
    lines = to_lines(text)
    if "## Status" not in lines:
        return "", lines
    start = lines.index("## Status") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(line for line in lines[start:end] if line.strip()), lines[:start] + lines[end:]


def valid_status(status: str) -> bool:
    m = STATUS.fullmatch(status)
    if not m:
        return False
    try:
        return not m["date"] or bool(datetime.date.fromisoformat(m["date"]))
    except ValueError:
        return False


def check_adrs(files: dict[str, str], living: dict[str, str]) -> list[str]:
    """Rules 1 to 5."""
    errors: list[str] = []
    adrs: dict[str, tuple[str, str]] = {}
    for name, text in sorted(files.items()):
        named = NAME.fullmatch(name)
        if not named:
            errors.append(f"{name}: the name must be NNNN-short-title.md")
            continue
        number, lines = named[1], to_lines(text)
        if number in adrs:
            errors.append(f"{name}: number {number} is already used")
        if not re.fullmatch(rf"# ADR {number} — \S.*", lines[0]):
            errors.append(f'{name}: the first line must be "# ADR {number} — title"')
        for section in SECTIONS:
            if lines.count(f"## {section}") != 1:
                errors.append(f"{name}: section {section} must be there once")
        status = split_status(text)[0]
        if number != TEMPLATE and not valid_status(status):
            errors.append(f"{name}: invalid status {status!r}")
        adrs[number] = (name, status)

    if sorted(adrs) != [f"{i:04}" for i in range(len(adrs) or 1)]:
        errors.append(f"{ADR_DIR}: numbers must run from {TEMPLATE} without gaps, found: {', '.join(sorted(adrs)) or 'none'}")

    cited = {number for text in living.values() for number in CITATION.findall(text)}
    for number, (name, status) in adrs.items():
        if number == TEMPLATE:
            continue
        if status.startswith("Accepted") and number not in cited:
            errors.append(f"{name}: accepted but cited in no living doc ({', '.join(living)})")
        m = STATUS.fullmatch(status)
        if not m or not m["by"]:
            continue
        by = m["by"]
        if by not in adrs:
            errors.append(f"{name}: superseding ADR {by} does not exist")
        elif by <= number:
            errors.append(f"{name}: superseding ADR {by} is not newer")
        else:
            by_name, by_status = adrs[by]
            if not by_status.startswith(("Accepted", "Superseded by")):
                errors.append(f"{name}: superseding ADR {by} is neither accepted nor superseded")
            if number not in CITATION.findall(files[by_name]):
                errors.append(f"{by_name}: must cite ADR {number}, which it supersedes")

    for doc, text in living.items():
        for number in sorted(set(CITATION.findall(text)) - {TEMPLATE}):
            if number not in adrs:
                errors.append(f"{doc}: cites ADR {number}, which does not exist")
            elif not adrs[number][1].startswith("Accepted"):
                errors.append(f"{doc}: cites ADR {number}, which is not accepted")
    return errors


def check_base(base: dict[str, str], files: dict[str, str]) -> list[str]:
    """Rule 6."""
    errors: list[str] = []
    for name, before in sorted(base.items()):
        status, body = split_status(before)
        if name.startswith(TEMPLATE) or not status.startswith(("Accepted", "Superseded by")):
            continue
        if name not in files:
            errors.append(f"{name}: accepted or superseded on the base, it cannot be deleted or renamed")
            continue
        new_status, new_body = split_status(files[name])
        if status.startswith("Superseded by"):
            if to_lines(files[name]) != to_lines(before):
                errors.append(f"{name}: superseded on the base, it cannot change")
            continue
        if new_body != body:
            errors.append(f"{name}: accepted on the base, nothing outside its Status section can change")
        if new_status != status and not new_status.startswith("Superseded by"):
            errors.append(f'{name}: accepted on the base, its status can only become "Superseded by", not {new_status!r}')
    return errors


def read_base(ref: str) -> dict[str, str]:
    mb = git("merge-base", ref, "HEAD").strip()
    paths = [p for p in git("ls-tree", "-z", "--name-only", mb, f"{ADR_DIR}/").split("\0") if p]
    return {Path(p).name: git("show", f"{mb}:{p}") for p in paths}


def self_test() -> int:
    def adr(number: str, status: str, context: str = "c") -> str:
        return f"# ADR {number} — T\n\n## Status\n\n{status}\n\n## Context\n\n{context}\n\n## Decision\n\nd\n\n## Consequences\n\ne\n"

    failures: list[str] = []

    def expect(label: str, errors: list[str], message: str | None = None) -> None:
        if not (errors == [] if message is None else len(errors) == 1 and message in errors[0]):
            failures.append(f"{label}: expected {message or 'no error'!r}, got {errors}")

    def check(label: str, message: str | None, files: dict[str, str], living: str = "") -> None:
        expect(label, check_adrs({"0000-template.md": adr("0000", "Any"), **files}, {"CLAUDE.md": living}), message)

    a, b = "0001-a.md", "0002-b.md"
    proposed, accepted = adr("0001", "Proposed"), adr("0001", "Accepted (2026-11-25).")
    superseded = adr("0001", "Superseded by ADR 0002 (2026-11-26).")
    newer = adr("0002", "Accepted (2026-11-26).", "Replaces ADR 0001.")

    check("1-2-3 ok", None, {a: proposed})
    check("1-2-3 ok with CRLF", None, {a: accepted.replace("\n", "\r\n")}, "ADR 0001")
    check("1 name", "name must be", {"note.md": proposed})
    check("1 duplicate", "number 0001 is already used", {a: proposed, "0001-b.md": proposed})
    check("1 gap", "without gaps, found: 0000, 0002", {b: adr("0002", "Proposed")})
    expect("1 empty folder", check_adrs({}, {}), "without gaps, found: none")
    check("1 first line", 'first line must be "# ADR 0001', {a: adr("0002", "Proposed")})
    check("1 template first line", 'first line must be "# ADR 0000', {"0000-template.md": adr("0001", "Any")})
    check("2 missing section", "section Decision must be there once", {a: proposed.replace("## Decision", "## Choice")})
    check("2 section twice", "section Status must be there once", {a: proposed + "\n## Status\n\nProposed\n"})
    check("2 template section", "section Context must be there once", {"0000-template.md": adr("0000", "Any").replace("## Context", "")})
    check("3 unknown", "invalid status 'Deprecated (2026-11-25).'", {a: adr("0001", "Deprecated (2026-11-25).")})
    check("3 no date", "invalid status 'Accepted'", {a: adr("0001", "Accepted")}, "ADR 0001")
    check("3 no such date", "invalid status 'Accepted (2026-13-01).'", {a: adr("0001", "Accepted (2026-13-01).")}, "ADR 0001")
    check("3 two lines", r"invalid status 'Proposed\nMore.'", {a: adr("0001", "Proposed\n\nMore.")})
    check("3 empty", "invalid status ''", {a: adr("0001", "")})

    check("4 ok", None, {a: superseded, b: newer}, "ADR 0002")
    chain = {a: superseded, b: newer.replace("Accepted (2026-11-26).", "Superseded by ADR 0003 (2026-11-27)."),
             "0003-c.md": adr("0003", "Accepted (2026-11-27).", "Replaces ADR-0002.")}
    check("4 ok chain", None, chain, "ADR 0003")
    check("4 missing", "superseding ADR 0002 does not exist", {a: superseded})
    check("4 not newer", "superseding ADR 0001 is not newer", {a: adr("0001", "Superseded by ADR 0001 (2026-11-26).")})
    check("4 proposed", "ADR 0002 is neither accepted nor superseded", {a: superseded, b: adr("0002", "Proposed", "ADR 0001")})
    check("4 not cited", "must cite ADR 0001", {a: superseded, b: adr("0002", "Accepted (2026-11-26).")}, "ADR 0002")

    check("5 ok", None, {a: accepted}, "ADR-0001, ADR NNNN and ADR 0000")
    check("5 ok template", None, {"0000-template.md": adr("0000", "Accepted (2026-11-25).")})
    check("5 not cited", "cited in no living doc", {a: accepted}, "ADR 00012")
    check("5 cites a missing one", "cites ADR 0007, which does not exist", {a: accepted}, "ADR 0001 ADR 0007")
    check("5 cites a proposed one", "cites ADR 0001, which is not accepted", {a: proposed}, "ADR 0001")
    check("5 cites a superseded one", "cites ADR 0001, which is not accepted", {a: superseded, b: newer}, "ADR 0001 ADR 0002")

    def change(label: str, message: str | None, before: str, files: dict[str, str]) -> None:
        expect(label, check_base({"0000-template.md": accepted, a: before}, files), message)

    change("6 ok unchanged with CRLF", None, accepted, {a: accepted.replace("\n", "\r\n")})
    change("6 ok superseded", None, accepted, {a: superseded, b: newer})
    change("6 ok superseded unchanged", None, superseded, {a: superseded.replace("\n", "\r\n")})
    change("6 ok proposed accepted", None, proposed, {a: accepted})
    change("6 ok proposed deleted", None, proposed, {})
    change("6 deleted", "0001-a.md: accepted or superseded on the base, it cannot be deleted or renamed", accepted, {})
    change("6 renamed", "0001-a.md: accepted or superseded on the base, it cannot be deleted or renamed", accepted, {"0001-b.md": accepted})
    change("6 body edited", "nothing outside its Status section can change", accepted, {a: accepted.replace("\nd\n", "\nother\n")})
    change("6 superseded and body edited", "nothing outside its Status section can change", accepted, {a: superseded + "more\n"})
    change("6 date changed", "not 'Accepted (2026-11-30).'", accepted, {a: adr("0001", "Accepted (2026-11-30).")})
    change("6 back to proposed", "not 'Proposed'", accepted, {a: proposed})
    change("6 superseded then edited", "superseded on the base, it cannot change", superseded, {a: superseded + "more\n"})
    change("6 superseded then accepted", "superseded on the base, it cannot change", superseded, {a: accepted})
    change("6 superseded then deleted", "cannot be deleted or renamed", superseded, {})

    for failure in failures:
        print(f"::error::self-test: {failure}")
    if not failures:
        print("self-test ok")
    return 1 if failures else 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args == ["--self-test"]:
        return self_test()
    if len(args) > 1 or (args and args[0].startswith("-")):
        print(__doc__)
        return 2
    try:
        files = {p.name: p.read_text(encoding="utf-8") for p in Path(ADR_DIR).iterdir()}
        living = {doc: Path(doc).read_text(encoding="utf-8") for doc in LIVING}
    except (OSError, UnicodeDecodeError) as e:
        print(f"::error::cannot read the ADRs or the living docs: {e}")
        return 1
    errors = check_adrs(files, living)
    if args:
        try:
            errors += check_base(read_base(args[0]), files)
        except subprocess.CalledProcessError as e:
            print(f"::error::cannot read base ref {args[0]!r}: {e.stderr.strip() or 'no merge base with HEAD'}")
            return 2
    for e in errors:
        print(f"::error::{e}")
    if errors:
        return 1
    print(f"decisions ok: {len(files) - 1} ADR(s)" + (", and the base ones are kept" if args else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
