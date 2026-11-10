#!/usr/bin/env python3
"""Grade an a11y-runtime-audit eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case:

    <run-dir>/
      broken-findings.md
      keyboard-popups.md
      clean-control.md

Each file holds the complete answer an agent gave, and nothing else. Grading is pure regex
over that text, no model in the loop. The axe assertions name rule ids on purpose: a rule
renamed or retagged in a new axe-core release fails the eval instead of vanishing.

Usage:
    grade.py <run-dir> [--json]

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

UNDERSTANDING = re.compile(r"https://www\.w3\.org/WAI/WCAG22/Understanding/[a-z0-9-]+\.html")


def lines_with(text: str, *patterns: str) -> list[str]:
    return [l for l in text.splitlines() if all(re.search(p, l, re.I) for p in patterns)]


def check(text: str, label: str, *patterns: str) -> tuple[str, bool, str]:
    hit = lines_with(text, *patterns)
    return (label, bool(hit), hit[0] if hit else "no line matches " + " + ".join(patterns))


def near(text: str, label: str, pattern: str) -> tuple[str, bool, str]:
    m = re.search(pattern, text, re.I)
    return (label, bool(m), m.group(0)[:200] if m else "no match for " + pattern)


def grade_broken(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    links = set(UNDERSTANDING.findall(text))
    return [
        check(text, "button-name under 4.1.2", r"button-name", r"4\.1\.2"),
        check(text, "color-contrast under 1.4.3", r"color-contrast", r"1\.4\.3"),
        check(text, "target-size under 2.5.8", r"target-size", r"2\.5\.8"),
        check(text, "Help link without focus indicator under 2.4.7", r"2\.4\.7", r"help|nofocus"),
        check(text, "link under the cookie bar under 2.4.11", r"2\.4\.11", r"cookie|skip to content"),
        check(text, "pointer-only Save div under 2.1.1", r"2\.1\.1", r"save|fake-btn"),
        check(text, "horizontal scroll at 320 px under 1.4.10", r"1\.4\.10", r"320"),
        ("at least five Understanding pages linked", len(links) >= 5, f"{len(links)} distinct links"),
    ]


def grade_popups(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    stops = re.findall(r"(?:^|\s)\d+\.\s+`[^`]+`", text)
    return [
        near(text, "settings dialog stays open on Escape",
             r"(open-modal|settings)[\s\S]{0,400}?escape[\s\S]{0,80}?(stays open|still open|remains open|does not close|doesn.t close|does nothing|ignored)"),
        check(text, "Actions menu loses focus, under 2.4.3", r"actions", r"2\.4\.3"),
        ("focus order printed as numbered Tab stops", bool(re.search(r"focus order", text, re.I)) and len(stops) >= 5, f"{len(stops)} numbered stops"),
        ("each popup finding has an Enter-then-Escape repro",
         all(re.search(rf"{t}[\s\S]{{0,400}}?enter[\s\S]{{0,400}}?escape", text, re.I) for t in (r"(open-modal|settings)", r"actions")),
         "dialog and menu each followed by Enter then Escape within 400 characters"),
        check(text, "result stated as FAIL with severity counts", r"\bFAIL\b", r"\d+ critical", r"\d+ serious"),
    ]


def grade_clean(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    bad = [l for l in text.splitlines()
           if re.search(r"\b(critical|serious)\b", l, re.I)
           and not re.search(r"\b0 critical\b|\b0 serious\b|no critical|no serious|not? .*critical or serious", l, re.I)]
    return [
        check(text, "page passes with no critical or serious finding", r"\bPASS\b|no critical or serious|no (wcag )?violations|nothing blocks"),
        ("no line reports a critical or serious finding", not bad, bad[0] if bad else "none"),
        check(text, "human checks named, screen reader included", r"screen.?reader"),
        check(text, "axe-core version named", r"axe-core\s+v?\d+\.\d+\.\d+"),
        ("both popups close on Escape and return focus",
         len(lines_with(text, r"open-modal|open settings|dialog", r"focus returns|returns focus|focus return")) > 0
         and len(lines_with(text, r"actions", r"focus returns|returns focus|focus return")) > 0,
         "dialog and menu both report focus returned"),
    ]


GRADERS = {
    "broken-findings": grade_broken,
    "keyboard-popups": grade_popups,
    "clean-control": grade_clean,
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
        results = grader(answer.read_text(), {})
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
