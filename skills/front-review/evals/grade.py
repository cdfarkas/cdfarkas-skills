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

A finding counts when one line names the file with a line number and the rule id, the
first line of the finding shape. An absence assertion passes only on an answer that is a
review at all (it carries a VERDICT line), so an empty answer scores 0.

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

VERDICT = re.compile(r"^VERDICT: (PASS|CHANGES)$", re.M)
OLDFIELD = re.compile(r"OldField\.tsx:\d+")
SWITCH = re.compile(r"Switch\.(?:tsx|module\.css):\d+")
PX44 = re.compile(r"\b44\s*(?:px|css|×|x\b|by)", re.I)
BOOLEAN = re.compile(r"\bR5\b|boolean prop|mode boolean|props? bool[ée]enne", re.I)
MEMO = re.compile(r"\bR7\b|dependency array|deps array|tableau de d[ée]pendances|useCallback|useMemo|React\.memo|\bmemoi[sz]", re.I)


def nonempty(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def finding(text: str, path: str, rule: str) -> tuple[bool, str]:
    loc = re.compile(path + r":\d+")
    rid = re.compile(rf"\b{rule}\b")
    hit = next((l for l in nonempty(text) if loc.search(l) and rid.search(l)), None)
    return hit is not None, hit or "missing"


def is_review(text: str) -> bool:
    return bool(VERDICT.search(text))


def absent(text: str, pattern: re.Pattern) -> tuple[bool, str]:
    if not is_review(text):
        return False, "no VERDICT line: not a review"
    hit = next((l for l in nonempty(text) if pattern.search(l)), None)
    return hit is None, hit or "absent"


def last_is_changes(text: str) -> tuple[bool, str]:
    lines = nonempty(text)
    last = lines[-1] if lines else ""
    return last == "VERDICT: CHANGES", last or "empty"


def line_starting(text: str, label: str) -> tuple[bool, str]:
    hit = next((l for l in nonempty(text) if re.match(rf"^\**{label}\**\s*:", l)), None)
    return hit is not None, hit or "missing"


def grade(spec: list[tuple], text: str) -> list[tuple[str, bool, str]]:
    out = []
    for label, fn, *args in spec:
        ok, evidence = fn(text, *args)
        out.append((label, ok, evidence))
    return out


def grade_full_review(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    return grade([
        ("A1 reported on src/Checkbox.module.css:line", finding, r"Checkbox\.module\.css", "A1"),
        ("R1 reported on src/Input.tsx:line", finding, r"Input\.tsx", "R1"),
        ("A2 reported on src/Button.module.css:line", finding, r"Button\.module\.css", "A2"),
        ("A3 reported on src/IconButton:line", finding, r"IconButton\.(?:tsx|module\.css)", "A3"),
        ("P1 reported on src/Button.tsx:line", finding, r"(?<!Icon)Button\.tsx", "P1"),
        ("the overlay-disabled R1 in OldField.tsx is not reported", absent, OLDFIELD),
        ("the last non-empty line is VERDICT: CHANGES", last_is_changes),
    ], text)


def grade_a11y_pass(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    return grade([
        ("A1 reported on src/Checkbox.module.css:line", finding, r"Checkbox\.module\.css", "A1"),
        ("A2 reported on src/Button.module.css:line", finding, r"Button\.module\.css", "A2"),
        ("A3 reported on src/IconButton:line", finding, r"IconButton\.(?:tsx|module\.css)", "A3"),
        ("no finding cites src/Switch (24 px meets the floor)", absent, SWITCH),
        ("no 44 px threshold is applied", absent, PX44),
        ("a Not checked line is present", line_starting, "Not checked"),
    ], text)


def grade_fr_pr_style(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    bloquant = (lambda t: (bool(re.search(r"^#+\s*Bloquant\b", t, re.M)),
                           "present" if re.search(r"^#+\s*Bloquant\b", t, re.M) else "missing"))
    return grade([
        ("the French section names are used (a Bloquant heading)", bloquant),
        ("a Non vérifié line is present", line_starting, "Non vérifié"),
        ("R1 reported on src/Input.tsx:line", finding, r"Input\.tsx", "R1"),
        ("the boolean invalid prop is not reported (X1)", absent, BOOLEAN),
        ("the dependency-less useLayoutEffect is not reported (X7)", absent, MEMO),
        ("the overlay-disabled R1 in OldField.tsx is not reported", absent, OLDFIELD),
        ("the last non-empty line is VERDICT: CHANGES", last_is_changes),
    ], text)


GRADERS = {
    "full-review": grade_full_review,
    "a11y-pass": grade_a11y_pass,
    "fr-pr-style": grade_fr_pr_style,
}


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
            "passed": sum(1 for _, ok, _ in results if ok),
            "total": len(results),
            "expectations": [{"text": t, "passed": ok, "evidence": ev[:200]} for t, ok, ev in results],
        }
        failed += sum(1 for _, ok, _ in results if not ok)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for name, res in report.items():
            if "error" in res:
                print(f"{name}: {res['error']}")
                continue
            print(f"{name}: {res['passed']}/{res['total']}")
            for e in res["expectations"]:
                if not e["passed"]:
                    print(f"  FAIL  {e['text']}\n        {e['evidence']}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
