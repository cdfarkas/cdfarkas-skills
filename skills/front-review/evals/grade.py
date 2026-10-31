#!/usr/bin/env python3
"""Grade a front-review eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case:

    <run-dir>/
      full-review.md
      a11y-pass.md
      fr-pr-style.md

Each file holds the complete answer an agent gave, and nothing else. Grading is pure
regex over that text, no model in the loop, so a rerun grades identically.

The fixture under evals/fixtures/sample-ui-lib/ plants, by construction:
  - A1  src/Checkbox.module.css   appearance: none, states drawn with background, no forced-colors path
  - R1  src/Input.tsx             {...rest} after aria-invalid, so a caller's aria-invalid wins over `invalid`
  - A2  src/Button.module.css     the only hover cue is a transform, removed under reduced motion
  - A3  src/IconButton.*          an 18 px target whose accessible name is optional
  - P1  src/Button.tsx            a module-level variant -> CSS-module class map (a hint: finding or Not checked)
  - R1  src/legacy/OldField.tsx   switched off by src/legacy/REVIEW.md: must NOT be reported
and three traps that must NOT be reported:
  - X1  the `invalid` boolean of Input mirrors one ARIA state
  - X7  Checkbox's dependency-less useLayoutEffect re-applies `indeterminate` after every render
  - X4  Switch's 24 px target meets SC 2.5.8; a 44 px rule would flag it

Grading credits substance, not the skill's vocabulary, so an agent without the skill is not
failed on format:
  - a citation is a file with a line in any common style: `path:12`, `path:12-25`, or the file
    followed by "line 12", "lines 17-25", "lignes 17 à 25", "(ligne 8)"; backticked or not,
    relative or absolute, with forward or back slashes
  - a finding counts when one finding unit cites the file AND carries either the rule id or the
    mechanism, in English or French; a unit is a paragraph, a list item, or a heading together
    with the paragraph under it
  - Not checked / Non vérifié lines and sections, and sections titled like What is good,
    Verified OK, Ce qui est bon, Not reported, Non reporté, are stripped before findings and
    absences are matched: a mention there is not a finding
  - P1 is a hint, not a mandatory candidate: it passes as a finding, or as a Not checked
    mention with a reason
  - an absence assertion passes on any review: a non-empty answer with at least one citation,
    so an empty answer scores 0
  - format assertions (the last VERDICT line, the Not checked line or section, the French
    section names) are scored separately, so the gap on substance can be read on its own

Usage:
    grade.py <run-dir>
    grade.py <run-dir> --json     # machine-readable

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SUBSTANCE, FORMAT = "substance", "format"

TAIL = r"(?::\d+|`?[\s,;:(]*(?:lines?|lignes?)\s+\d+)"
LOC = re.compile(r"[\w.\\/-]+\.(?:tsx|ts|jsx|js|css|json|md)" + TAIL, re.I)
OLDFIELD = re.compile(r"OldField\.tsx" + TAIL, re.I)
SWITCH = re.compile(r"(?:^|[\\/`])Switch\.(?:tsx|module\.css)", re.I)
TARGET = re.compile(r"size|taille|\b24\b|\b44\b|target|cible", re.I)
PX44 = re.compile(r"\b44\s*(?:px|css|×|x\b|by)", re.I)
BOOLEAN = re.compile(r"\bR5\b|boolean prop|mode boolean|props? bool[ée]enne", re.I)
MEMO = re.compile(r"\bR7\b|dependency array|deps array|tableau de d[ée]pendances|useCallback|useMemo|React\.memo|\bmemoi[sz]", re.I)
REASON = re.compile(r"because|since|\bno\b|\bnot\b|without|cannot|unmeasured|\bcar\b|parce|faute|\bsans\b|aucun|\bpas\b|impossible", re.I)

CHECKBOX_CSS = r"Checkbox\.module\.css"
INPUT_TSX = r"(?<!Old)Input\.tsx"
BUTTON_CSS = r"(?<!Icon)Button\.module\.css"
ICONBUTTON = r"IconButton\.(?:tsx|module\.css)"
BUTTON_TSX = r"(?<!Icon)Button\.tsx"

NOT_CHECKED = re.compile(r"^\**(?:Not checked|Non v[ée]rifi[ée])\**\s*:", re.I)
OUT_OF_SCOPE = re.compile(
    r"^(#+)\s*\**(?:(Not checked|Non v[ée]rifi[ée])|What is good|Verified OK|Ce qui est bon|Not reported|Non report[ée])", re.I)
HEADING = re.compile(r"^(#+)\s")
ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s")

# Matched against one finding unit joined into a single line; (?=…)(?=…) means every term, in any order.
MECHANISM = {
    "A1": re.compile(r"forced[- ]colou?rs|high[- ]contrast|contrastes? [ée]lev[ée]s?|couleurs forc[ée]es", re.I),
    "R1": re.compile(
        r"(?=.*(?:\.\.\.\s*(?:rest|props)|spread|d[ée]compos))"
        r"(?=.*(?:aria-invalid|after|last|order|overrid|wins|apr[èe]s|ordre|[ée]cras|l'emporte))"
        r"|(?=.*aria-invalid)(?=.*(?:overrid|wins|clobber|[ée]cras|l'emporte|prend le dessus))", re.I),
    "A2": re.compile(
        r"(?=.*(?:reduced[- ]motion|mouvements? r[ée]duits?|r[ée]duction des mouvements))(?=.*(?:hover|survol))"
        r"(?=.*(?:\bno\b|nothing|none|only|lost|loses?\b|remov|without|disappear|\baucun|\brien\b|\bsans\b|\bseul|perd|dispara))",
        re.I),
    "A3": re.compile(
        r"target[- ]size|touch target|hit (?:area|target)|taille (?:de |des )?cibles?|cible tactile"
        r"|\b24\s*(?:css\s*)?(?:px|×|x\b)|2\.5\.8", re.I),
    "P1": re.compile(r"tree[- ]?shak|bundl|(?:variant|class|size|sizeClass)[- ]?(?:map|lookup)|lookup (?:map|table|object)", re.I),
}


def nonempty(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def split_scope(text: str) -> tuple[str, str]:
    """Return (the text findings are matched in, the Not checked text)."""
    kept, unchecked = [], []
    skip, skip_level, note_section, in_note = False, 0, False, False
    for line in text.splitlines():
        s = line.strip()
        head = HEADING.match(s)
        if head and skip and len(head.group(1)) <= skip_level:
            skip = False
        if head or not s:
            in_note = False
        out = OUT_OF_SCOPE.match(s)
        if out:
            skip, skip_level, note_section = True, len(out.group(1)), bool(out.group(2))
            continue
        if NOT_CHECKED.match(s):
            in_note = True
        if in_note or (skip and note_section):
            unchecked.append(line)
        elif not skip:
            kept.append(line)
    return "\n".join(kept), "\n".join(unchecked)


def units(text: str) -> list[str]:
    out, cur, bare_heading = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if cur and not bare_heading:
                out.append(" ".join(cur))
                cur = []
            continue
        if HEADING.match(s) or ITEM.match(s):
            if cur:
                out.append(" ".join(cur))
            cur, bare_heading = [s], bool(HEADING.match(s))
            continue
        cur.append(s)
        bare_heading = False
    if cur:
        out.append(" ".join(cur))
    return out


def finding(text: str, path: str, rule: str) -> tuple[bool, str]:
    loc, rid = re.compile(path + TAIL, re.I), re.compile(rf"\b{rule}\b")
    hit = next((u for u in units(split_scope(text)[0])
                if loc.search(u) and (rid.search(u) or MECHANISM[rule].search(u))), None)
    return hit is not None, hit or "missing"


def p1_hint(text: str) -> tuple[bool, str]:
    ok, evidence = finding(text, BUTTON_TSX, "P1")
    if ok:
        return ok, evidence
    loc = re.compile(BUTTON_TSX + TAIL, re.I)
    note = next((u for u in units(split_scope(text)[1])
                 if (re.search(r"\bP1\b|sizeClass", u) or loc.search(u)) and REASON.search(u)), None)
    return note is not None, note or "neither a finding nor a Not checked mention with a reason"


def is_review(text: str) -> bool:
    return bool(LOC.search(text))


def absent(text: str, pattern: re.Pattern) -> tuple[bool, str]:
    if not is_review(text):
        return False, "no file:line citation: not a review"
    hit = next((l for l in nonempty(split_scope(text)[0]) if pattern.search(l)), None)
    return hit is None, hit or "absent"


def no_switch_target(text: str) -> tuple[bool, str]:
    """Fails only on a unit whose first citation is the Switch and that talks about its size."""
    if not is_review(text):
        return False, "no file:line citation: not a review"
    for u in units(split_scope(text)[0]):
        first = LOC.search(u)
        if first and SWITCH.search(first.group(0)) and TARGET.search(u):
            return False, u
    return True, "absent"


def last_is_changes(text: str) -> tuple[bool, str]:
    lines = nonempty(text)
    last = lines[-1] if lines else ""
    return last == "VERDICT: CHANGES", last or "empty"


def line_starting(text: str, label: str) -> tuple[bool, str]:
    hit = next((l for l in nonempty(text) if re.match(rf"^(?:#+\s*)?\**{label}\**\s*(?::|$)", l, re.I)), None)
    return hit is not None, hit or "missing"


def bloquant(text: str) -> tuple[bool, str]:
    hit = re.search(r"^#+\s*Bloquant\b.*$", text, re.M)
    return hit is not None, hit.group(0) if hit else "missing"


def grade(spec: list[tuple], text: str) -> list[tuple[str, bool, str, str]]:
    out = []
    for kind, label, fn, *args in spec:
        ok, evidence = fn(text, *args)
        out.append((label, ok, evidence, kind))
    return out


def grade_full_review(text: str, ctx: dict) -> list[tuple[str, bool, str, str]]:
    return grade([
        (SUBSTANCE, "A1 (forced colors) reported on src/Checkbox.module.css:line", finding, CHECKBOX_CSS, "A1"),
        (SUBSTANCE, "R1 (spread after aria-invalid) reported on src/Input.tsx:line", finding, INPUT_TSX, "R1"),
        (SUBSTANCE, "A2 (reduced-motion hover cue) reported on src/Button.module.css:line", finding, BUTTON_CSS, "A2"),
        (SUBSTANCE, "A3 (target size) reported on src/IconButton:line", finding, ICONBUTTON, "A3"),
        (SUBSTANCE, "P1 (variant map hint) reported on src/Button.tsx:line, or in Not checked with a reason", p1_hint),
        (SUBSTANCE, "the overlay-disabled R1 in OldField.tsx is not reported", absent, OLDFIELD),
        (FORMAT, "the last non-empty line is VERDICT: CHANGES", last_is_changes),
    ], text)


def grade_a11y_pass(text: str, ctx: dict) -> list[tuple[str, bool, str, str]]:
    return grade([
        (SUBSTANCE, "A1 (forced colors) reported on src/Checkbox.module.css:line", finding, CHECKBOX_CSS, "A1"),
        (SUBSTANCE, "A2 (reduced-motion hover cue) reported on src/Button.module.css:line", finding, BUTTON_CSS, "A2"),
        (SUBSTANCE, "A3 (target size) reported on src/IconButton:line", finding, ICONBUTTON, "A3"),
        (SUBSTANCE, "no finding on the Switch target size (24 px meets the floor)", no_switch_target),
        (SUBSTANCE, "no 44 px threshold is applied", absent, PX44),
        (FORMAT, "a Not checked line or section is present", line_starting, "Not checked"),
    ], text)


def grade_fr_pr_style(text: str, ctx: dict) -> list[tuple[str, bool, str, str]]:
    return grade([
        (FORMAT, "the French section names are used (a Bloquant heading)", bloquant),
        (FORMAT, "a Non vérifié line or section is present", line_starting, "Non v[ée]rifi[ée]"),
        (SUBSTANCE, "R1 (spread after aria-invalid) reported on src/Input.tsx:line", finding, INPUT_TSX, "R1"),
        (SUBSTANCE, "the boolean invalid prop is not reported (X1)", absent, BOOLEAN),
        (SUBSTANCE, "the dependency-less useLayoutEffect is not reported (X7)", absent, MEMO),
        (SUBSTANCE, "the overlay-disabled R1 in OldField.tsx is not reported", absent, OLDFIELD),
        (FORMAT, "the last non-empty line is VERDICT: CHANGES", last_is_changes),
    ], text)


GRADERS = {
    "full-review": grade_full_review,
    "a11y-pass": grade_a11y_pass,
    "fr-pr-style": grade_fr_pr_style,
}


def score(results: list[tuple], kind: str | None = None) -> dict:
    picked = [r for r in results if kind is None or r[3] == kind]
    return {"passed": sum(1 for r in picked if r[1]), "total": len(picked)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report, failed = {}, 0

    for name, grader in GRADERS.items():
        answer = args.run_dir / f"{name}.md"
        if not answer.exists():
            report[name] = {"error": f"missing {answer}"}
            failed += 1
            continue
        results = grader(answer.read_text(encoding="utf-8"), {})
        report[name] = {
            **score(results),
            SUBSTANCE: score(results, SUBSTANCE),
            FORMAT: score(results, FORMAT),
            "expectations": [{"text": t, "kind": k, "passed": ok, "evidence": ev[:200]} for t, ok, ev, k in results],
        }
        failed += sum(1 for r in results if not r[1])

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for name, res in report.items():
            if "error" in res:
                print(f"{name}: {res['error']}")
                continue
            s, f = res[SUBSTANCE], res[FORMAT]
            print(f"{name}: substance {s['passed']}/{s['total']}  format {f['passed']}/{f['total']}  "
                  f"total {res['passed']}/{res['total']}")
            for e in res["expectations"]:
                if not e["passed"]:
                    print(f"  FAIL  [{e['kind']}] {e['text']}\n        {e['evidence']}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
