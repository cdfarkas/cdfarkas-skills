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
  - P1  src/Button.tsx            a module-level variant -> CSS-module class map, in a publishable package
  - R1  src/legacy/OldField.tsx   switched off by src/legacy/REVIEW.md: must NOT be reported
and three traps that must NOT be reported:
  - X1  the `invalid` boolean of Input mirrors one ARIA state
  - X7  Checkbox's dependency-less useLayoutEffect re-applies `indeterminate` after every render
  - X4  Switch's 24 px target meets SC 2.5.8; a 44 px rule would flag it

Grading credits substance, not the skill's vocabulary, so an agent without the skill is not
failed on format:
  - a finding counts when a window of up to 3 consecutive non-empty lines cites the file with
    a line number AND either the rule id or the mechanism, in English or French
  - an absence assertion passes on any review: a non-empty answer citing at least one
    file:line, so an empty answer scores 0
  - format assertions (the last VERDICT line, the Not checked line, the French section names)
    are scored separately, so the gap on substance can be read on its own

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

LOC = re.compile(r"[\w./-]+\.(?:tsx|ts|jsx|js|css|json|md):\d+")
OLDFIELD = re.compile(r"OldField\.tsx:\d+")
SWITCH = re.compile(r"Switch\.(?:tsx|module\.css):\d+")
PX44 = re.compile(r"\b44\s*(?:px|css|×|x\b|by)", re.I)
BOOLEAN = re.compile(r"\bR5\b|boolean prop|mode boolean|props? bool[ée]enne", re.I)
MEMO = re.compile(r"\bR7\b|dependency array|deps array|tableau de d[ée]pendances|useCallback|useMemo|React\.memo|\bmemoi[sz]", re.I)

CHECKBOX_CSS = r"Checkbox\.module\.css"
INPUT_TSX = r"(?<!Old)Input\.tsx"
BUTTON_CSS = r"(?<!Icon)Button\.module\.css"
ICONBUTTON = r"IconButton\.(?:tsx|module\.css)"
BUTTON_TSX = r"(?<!Icon)Button\.tsx"

# Matched against one window joined into a single line; (?=…)(?=…) means both terms, in any order.
MECHANISM = {
    "A1": re.compile(r"forced[- ]colou?rs|high[- ]contrast|contrastes? [ée]lev[ée]s?|couleurs forc[ée]es", re.I),
    "R1": re.compile(
        r"(?=.*(?:\.\.\.\s*(?:rest|props)|spread|d[ée]compos))"
        r"(?=.*(?:aria-invalid|after|last|order|overrid|wins|apr[èe]s|ordre|[ée]cras|l'emporte))"
        r"|(?=.*aria-invalid)(?=.*(?:overrid|wins|clobber|[ée]cras|l'emporte|prend le dessus))", re.I),
    "A2": re.compile(
        r"(?=.*(?:reduced[- ]motion|mouvements? r[ée]duits?|r[ée]duction des mouvements))(?=.*(?:hover|survol))", re.I),
    "A3": re.compile(
        r"target[- ]size|touch target|hit (?:area|target)|taille (?:de |des )?cibles?|cible tactile"
        r"|\b24\s*(?:css\s*)?(?:px|×|x\b)|2\.5\.8", re.I),
    "P1": re.compile(r"tree[- ]?shak|bundl|(?:variant|class|size|sizeClass)[- ]?(?:map|lookup)|lookup (?:map|table|object)", re.I),
}


def nonempty(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def finding(text: str, path: str, rule: str) -> tuple[bool, str]:
    loc = re.compile(path + r":\d+")
    rid = re.compile(rf"\b{rule}\b")
    lines = nonempty(text)
    windows = (" ".join(lines[i:i + 3]) for i in range(len(lines)))
    hit = next((w for w in windows if loc.search(w) and (rid.search(w) or MECHANISM[rule].search(w))), None)
    return hit is not None, hit or "missing"


def is_review(text: str) -> bool:
    return bool(LOC.search(text))


def absent(text: str, pattern: re.Pattern) -> tuple[bool, str]:
    if not is_review(text):
        return False, "no file:line citation: not a review"
    hit = next((l for l in nonempty(text) if pattern.search(l)), None)
    return hit is None, hit or "absent"


def last_is_changes(text: str) -> tuple[bool, str]:
    lines = nonempty(text)
    last = lines[-1] if lines else ""
    return last == "VERDICT: CHANGES", last or "empty"


def line_starting(text: str, label: str) -> tuple[bool, str]:
    hit = next((l for l in nonempty(text) if re.match(rf"^\**{label}\**\s*:", l)), None)
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
        (SUBSTANCE, "P1 (variant map vs tree-shaking) reported on src/Button.tsx:line", finding, BUTTON_TSX, "P1"),
        (SUBSTANCE, "the overlay-disabled R1 in OldField.tsx is not reported", absent, OLDFIELD),
        (FORMAT, "the last non-empty line is VERDICT: CHANGES", last_is_changes),
    ], text)


def grade_a11y_pass(text: str, ctx: dict) -> list[tuple[str, bool, str, str]]:
    return grade([
        (SUBSTANCE, "A1 (forced colors) reported on src/Checkbox.module.css:line", finding, CHECKBOX_CSS, "A1"),
        (SUBSTANCE, "A2 (reduced-motion hover cue) reported on src/Button.module.css:line", finding, BUTTON_CSS, "A2"),
        (SUBSTANCE, "A3 (target size) reported on src/IconButton:line", finding, ICONBUTTON, "A3"),
        (SUBSTANCE, "no finding cites src/Switch (24 px meets the floor)", absent, SWITCH),
        (SUBSTANCE, "no 44 px threshold is applied", absent, PX44),
        (FORMAT, "a Not checked line is present", line_starting, "Not checked"),
    ], text)


def grade_fr_pr_style(text: str, ctx: dict) -> list[tuple[str, bool, str, str]]:
    return grade([
        (FORMAT, "the French section names are used (a Bloquant heading)", bloquant),
        (FORMAT, "a Non vérifié line is present", line_starting, "Non vérifié"),
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
