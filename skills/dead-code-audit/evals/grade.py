#!/usr/bin/env python3
"""Grade a dead-code-audit eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case:

    <run-dir>/
      findings.md
      score.md
      guardrails.md

Each file holds the complete answer an agent gave, and nothing else. The skill's
script is prompt-independent — it prints the same categorized report whatever the
question — so the three files are the same report graded on different slices.
Grading is pure regex over that text, no model in the loop, so the committed
fixture grades the same way every time.

The fixture under evals/fixtures/sample-ts-project/ plants, by construction:
  - one genuinely dead file (src/unused-widget.ts)
  - one unused export (src/api.ts buildLegacyUrl)
  - one unused exported type (src/types.ts DeprecatedPayload)
  - one unused dependency (left-pad)
  - two live guardrail traps Knip still flags: a dynamic-import target
    (src/plugins/plugin-a.ts) and a config-referenced file (src/registry.ts)

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

HEADER = re.compile(r"Dead-code audit · sample-ts-project · \d{4}-\d{2}-\d{2} · Knip")
EXPORT = re.compile(r"src/api\.ts:\d+\s+buildLegacyUrl")
TYPE = re.compile(r"src/types\.ts:\d+\s+DeprecatedPayload")
CANDIDATE = "Before/after score (candidates — verify against the guardrails before removing)"
SECTIONS = (
    "Unused files",
    "Unused exports",
    "Unused exported types",
    "Unused dependencies",
    "Unlisted / undeclared dependencies",
)


def nonempty(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def grade_findings(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    first = lines[0] if lines else ""
    return [
        ("header names the fixture and Knip, with no 'defaults' suffix",
         bool(HEADER.fullmatch(first)),
         first),
        ("the genuinely dead file is reported under Unused files",
         "- src/unused-widget.ts" in text,
         "present" if "- src/unused-widget.ts" in text else "missing"),
        ("the Unused files count is 3",
         "Unused files (3)" in text,
         next((l for l in lines if l.startswith("Unused files")), "no section")),
        ("the planted unused export is reported with file:line",
         bool(EXPORT.search(text)),
         next((l for l in lines if "buildLegacyUrl" in l), "missing")),
        ("the planted unused exported type is reported with file:line",
         bool(TYPE.search(text)),
         next((l for l in lines if "DeprecatedPayload" in l), "missing")),
        ("the planted unused dependency is reported",
         "Unused dependencies (1)" in text and "- left-pad" in text,
         next((l for l in lines if "left-pad" in l), "missing")),
        ("every category section is present",
         all(s in text for s in SECTIONS),
         ", ".join(s for s in SECTIONS if s not in text) or "all present"),
    ]


def grade_score(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    loc = "- removable lines of code: 18 across 3 unused file(s)"
    deps = "- unused dependencies: 1"
    consistent = "Unused files (3)" in text and "across 3 unused file(s)" in text
    return [
        ("the score block frames its numbers as candidates to verify",
         CANDIDATE in text,
         "present" if CANDIDATE in text else "absent"),
        ("removable lines of code equal the planted 18 across 3 files",
         loc in text,
         next((l for l in lines if "removable lines of code" in l), "missing")),
        ("the unused-dependency count equals the planted 1",
         deps in text,
         next((l for l in lines if l.startswith("- unused dependencies")), "missing")),
        ("the score file count agrees with the Unused files section",
         consistent,
         "3 == 3" if consistent else "mismatch"),
    ]


def grade_guardrails(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    dyn = "- src/plugins/plugin-a.ts" in text
    cfg = "- src/registry.ts" in text
    dead = "- src/unused-widget.ts" in text
    return [
        ("the dynamic-import target is surfaced as a candidate",
         dyn,
         "present" if dyn else "missing"),
        ("the config-referenced file is surfaced as a candidate",
         cfg,
         "present" if cfg else "missing"),
        ("the script frames findings as candidates, not verdicts",
         CANDIDATE in text,
         "present" if CANDIDATE in text else "absent"),
        ("the genuinely dead file sits in the same undifferentiated list",
         dyn and cfg and dead,
         "all three unused files present" if (dyn and cfg and dead) else "not all present"),
    ]


GRADERS = {
    "findings": grade_findings,
    "score": grade_score,
    "guardrails": grade_guardrails,
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
