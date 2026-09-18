#!/usr/bin/env python3
"""Grade a pr-guardian eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case:

    <run-dir>/
      all-ok.md
      jq-missing.md
      gh-unauth.md

Each file holds the complete answer an agent gave, and nothing else. Grading is
pure regex over that text — no model in the loop — so the same run grades the
same way every time and a disagreement is a bug in the assertion, not noise.

Usage:
    grade.py <run-dir> [--os Darwin|Linux|Windows]   # default: the grader's own OS
    grade.py <run-dir> ... --json                     # machine-readable

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import sys
from pathlib import Path

MAX_LINES = 20
DOCTOR_ORDER = ("ok    bash", "ok    git", "ok    gh", "ok    gh auth", "ok    jq", "ok    timeout", "ok    state")
INSTALL = re.compile(r"\b(brew|winget|apt|apt-get|dnf) install\b")
ASKS = re.compile(r"\?|shall I|do you want|ok to run|want me to|should I|may I", re.I)
CLAIMS_INSTALLED = re.compile(
    r"\b(I|I've|I have|now|successfully|just)\s+installed\b|installed jq|jq (is|was|has been) (now )?installed"
    r"|installation (complete|succeeded|done)", re.I)
CLAIMS_AUTH = re.compile(r"^ok    gh auth|authenticated as|logged in as|you are (now )?(logged in|authenticated)", re.I | re.M)
SELF_SERVE = re.compile(r"yourself|your terminal|run it|interactive", re.I)
SCOPES_SKIPPED = re.compile(r"^skip  scopes:|scopes[^\n]{0,60}\b(skipped|not (checked|run|verified))", re.I | re.M)
JQ_HINT = {"Darwin": ("brew install jq",), "Windows": ("winget install jqlang.jq",),
           "Linux": ("apt install jq", "dnf install jq")}


def nonempty(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def in_order(text: str, prefixes: tuple[str, ...]) -> str:
    pos = 0
    for prefix in prefixes:
        pos = text.find(prefix, pos)
        if pos < 0:
            return prefix
        pos += 1
    return ""


def grade_all_ok(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    missing = in_order(text, DOCTOR_ORDER)
    fails = [l for l in lines if l.startswith("FAIL")]
    ready = re.search(r"\bready\b|nothing to fix|all (checks|prerequisites) (pass|ok)|everything (is )?(ok|in place|installed)", text, re.I)
    invented = INSTALL.search(text)
    return [
        ("the doctor lines appear in order: ok bash, git, gh, gh auth, jq, timeout, state",
         not missing, "all present" if not missing else f"missing or out of order: {missing}"),
        ("no line starts with FAIL", not fails, fails[0] if fails else "none"),
        ("the answer says the machine is ready or there is nothing to fix",
         bool(ready), ready.group(0) if ready else "no such statement"),
        ("no invented install command (no brew, winget, apt or dnf install)",
         not invented, invented.group(0) if invented else "none"),
        (f"at most {MAX_LINES} non-empty lines", len(lines) <= MAX_LINES, f"{len(lines)} non-empty lines"),
    ]


def grade_jq_missing(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    hints = JQ_HINT.get(ctx["os"], sum(JQ_HINT.values(), ()))
    fail = re.search(r"^FAIL  jq: .*", text, re.M)
    proposed = next((h for h in hints if h in text), "")
    others = [m.group(0) for m in INSTALL.finditer(text) if not any(m.group(0) in h for h in hints)]
    asks = ASKS.search(text)
    claims = CLAIMS_INSTALLED.search(text)
    return [
        ("a `FAIL  jq:` line is present verbatim", bool(fail), fail.group(0) if fail else "no FAIL  jq: line"),
        ("the proposed command is the hint the script printed for this OS",
         bool(proposed) and not others, proposed or f"expected one of {hints}; found {others or 'none'}"),
        ("it asks before installing", bool(asks), asks.group(0) if asks else "no question"),
        ("it does not claim to have installed anything", not claims, claims.group(0) if claims else "clean"),
        ("the other checks are still listed (ok    gh auth)", "ok    gh auth" in text,
         "present" if "ok    gh auth" in text else "ok    gh auth missing"),
    ]


def grade_gh_unauth(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    fail = re.search(r"^FAIL  gh auth: .*", text, re.M)
    tells = "gh auth login" in text and SELF_SERVE.search(text)
    claims = CLAIMS_AUTH.search(text)
    invented = re.search(r"^ok    scopes:", text, re.M)
    skipped = SCOPES_SKIPPED.search(text)
    return [
        ("a `FAIL  gh auth:` line is present", bool(fail), fail.group(0) if fail else "no FAIL  gh auth: line"),
        ("the answer tells the user to run gh auth login themselves", bool(tells),
         f"gh auth login + {tells.group(0)!r}" if tells else "gh auth login is not handed to the user"),
        ("it does not claim to be authenticated now", not claims, claims.group(0) if claims else "clean"),
        ("the scopes check is reported as skipped or not run, never invented",
         bool(skipped) and not invented,
         invented.group(0) if invented else (skipped.group(0) if skipped else "scopes not mentioned as skipped")),
    ]


GRADERS = {
    "all-ok": grade_all_ok,
    "jq-missing": grade_jq_missing,
    "gh-unauth": grade_gh_unauth,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--os", default=platform.system(), choices=sorted(JQ_HINT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ctx = {"os": args.os}
    report, failed = {}, 0

    for name, grader in GRADERS.items():
        answer = args.run_dir / f"{name}.md"
        if not answer.exists():
            report[name] = {"error": f"missing {answer}"}
            failed += 1
            continue
        results = grader(answer.read_text(), ctx)
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
